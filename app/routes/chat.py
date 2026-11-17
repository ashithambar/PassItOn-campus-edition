from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, abort
from flask_login import login_required, current_user
from app.models import db, Conversation, Message, Listing, User
from app.utils import create_notification

chat_bp = Blueprint('chat', __name__)

@chat_bp.route('/')
@login_required
def index():
    # Find all conversations involving current_user
    conversations = Conversation.query.filter(
        db.or_(
            Conversation.user1_id == current_user.id,
            Conversation.user2_id == current_user.id
        )
    ).order_by(Conversation.updated_at.desc()).all()
    
    active_convo_id = request.args.get('convo_id', type=int)
    active_convo = None
    
    if active_convo_id:
        active_convo = db.session.get(Conversation, active_convo_id)
        if active_convo and current_user.id not in (active_convo.user1_id, active_convo.user2_id):
            abort(403)
    elif conversations:
        active_convo = conversations[0]
        
    messages = []
    if active_convo:
        # Mark unread messages as read
        unread_msgs = Message.query.filter_by(
            conversation_id=active_convo.id,
            is_read=False
        ).filter(Message.sender_id != current_user.id).all()
        
        for m in unread_msgs:
            m.is_read = True
        db.session.commit()
        
        messages = Message.query.filter_by(conversation_id=active_convo.id).order_by(Message.created_at.asc()).all()

    return render_template(
        'chat/index.html',
        conversations=conversations,
        active_convo=active_convo,
        messages=messages
    )


@chat_bp.route('/start/<int:listing_id>')
@login_required
def start(listing_id):
    listing = db.session.get(Listing, listing_id)
    if not listing:
        abort(404)
        
    if listing.seller_id == current_user.id:
        flash("You cannot start a chat with yourself.", "warning")
        return redirect(url_for('listings.detail', listing_id=listing.id))
        
    # Check if conversation already exists between these 2 users regarding this listing (or generally)
    convo = Conversation.query.filter(
        db.or_(
            db.and_(Conversation.user1_id == current_user.id, Conversation.user2_id == listing.seller_id),
            db.and_(Conversation.user1_id == listing.seller_id, Conversation.user2_id == current_user.id)
        ),
        Conversation.listing_id == listing.id
    ).first()
    
    if not convo:
        # Create new conversation
        convo = Conversation(
            listing_id=listing.id,
            user1_id=current_user.id,
            user2_id=listing.seller_id
        )
        db.session.add(convo)
        db.session.flush()
        
        # Send initial automated friendly greeting
        initial_msg = Message(
            conversation_id=convo.id,
            sender_id=current_user.id,
            content=f"Hi {listing.seller.name}! I am interested in your listing '{listing.title}' (₹{int(listing.price)}). Is it still available?"
        )
        db.session.add(initial_msg)
        db.session.commit()
        
        create_notification(
            user_id=listing.seller_id,
            title="New Chat Message!",
            message=f"{current_user.name} messaged you regarding '{listing.title}'.",
            link=url_for('chat.index', convo_id=convo.id),
            notification_type='new_message'
        )
        
    return redirect(url_for('chat.index', convo_id=convo.id))


@chat_bp.route('/send/<int:conversation_id>', methods=['POST'])
@login_required
def send_message(conversation_id):
    convo = db.session.get(Conversation, conversation_id)
    if not convo or current_user.id not in (convo.user1_id, convo.user2_id):
        abort(403)
        
    content = request.form.get('content', '').strip()
    if not content and request.is_json:
        data = request.get_json() or {}
        content = data.get('content', '').strip()
        
    if not content:
        if request.is_json:
            return jsonify({'error': 'Message content cannot be empty'}), 400
        return redirect(url_for('chat.index', convo_id=convo.id))
        
    msg = Message(
        conversation_id=convo.id,
        sender_id=current_user.id,
        content=content
    )
    convo.updated_at = datetime.utcnow()
    db.session.add(msg)
    db.session.commit()
    
    # Notify recipient
    recipient = convo.other_user(current_user.id)
    create_notification(
        user_id=recipient.id,
        title=f"Message from {current_user.name}",
        message=f"{current_user.name}: {content[:60]}...",
        link=url_for('chat.index', convo_id=convo.id),
        notification_type='new_message'
    )
    
    if request.is_json:
        return jsonify({
            'success': True,
            'message': {
                'id': msg.id,
                'content': msg.content,
                'sender_id': msg.sender_id,
                'created_at': msg.created_at.strftime('%I:%M %p')
            }
        })
        
    return redirect(url_for('chat.index', convo_id=convo.id))


@chat_bp.route('/api/messages/<int:conversation_id>')
@login_required
def get_messages(conversation_id):
    convo = db.session.get(Conversation, conversation_id)
    if not convo or current_user.id not in (convo.user1_id, convo.user2_id):
        return jsonify({'error': 'Unauthorized'}), 403
        
    # Mark incoming unread as read
    unread_msgs = Message.query.filter_by(
        conversation_id=convo.id,
        is_read=False
    ).filter(Message.sender_id != current_user.id).all()
    for m in unread_msgs:
        m.is_read = True
    db.session.commit()
    
    messages = Message.query.filter_by(conversation_id=convo.id).order_by(Message.created_at.asc()).all()
    return jsonify({
        'messages': [{
            'id': m.id,
            'sender_id': m.sender_id,
            'sender_name': m.sender.name,
            'content': m.content,
            'is_me': m.sender_id == current_user.id,
            'created_at': m.created_at.strftime('%I:%M %p')
        } for m in messages]
    })

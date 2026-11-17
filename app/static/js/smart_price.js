// PassItOn – Live Smart Price Suggestion

document.addEventListener('DOMContentLoaded', function () {
    const categorySelect = document.getElementById('category_id');
    const conditionSelect = document.getElementById('condition');
    const origPriceInput = document.getElementById('original_price');
    const ageInput = document.getElementById('item_age_months');
    const priceInput = document.getElementById('price');
    
    const suggestionBox = document.getElementById('smart-price-container');
    const rangeText = document.getElementById('smart-price-range');
    const explanationText = document.getElementById('smart-price-explanation');
    const applyBtn = document.getElementById('btn-apply-smart-price');

    if (!categorySelect || !conditionSelect || !priceInput || !suggestionBox) {
        return;
    }

    let debounceTimer = null;
    let currentSuggestedPrice = 0;

    function fetchSmartPrice() {
        const catId = categorySelect.value;
        const condition = conditionSelect.value;
        const origPrice = origPriceInput ? origPriceInput.value : '';
        const ageMonths = ageInput ? ageInput.value : 0;

        if (!catId) {
            suggestionBox.style.display = 'none';
            return;
        }

        const params = new URLSearchParams({
            category_id: catId,
            condition: condition,
            original_price: origPrice || 0,
            item_age_months: ageMonths || 0
        });

        fetch(`/listings/api/smart-price?${params.toString()}`)
            .then(res => res.json())
            .then(data => {
                if (data && data.suggested_price) {
                    currentSuggestedPrice = data.suggested_price;
                    rangeText.innerText = `₹${data.min_price} – ₹${data.max_price}`;
                    explanationText.innerText = data.explanation;
                    applyBtn.innerText = `Use Suggested Price: ₹${data.suggested_price}`;
                    suggestionBox.style.display = 'block';
                }
            })
            .catch(err => {
                console.error("Smart price fetch error:", err);
            });
    }

    function triggerCalculation() {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(fetchSmartPrice, 350);
    }

    categorySelect.addEventListener('change', triggerCalculation);
    conditionSelect.addEventListener('change', triggerCalculation);
    if (origPriceInput) origPriceInput.addEventListener('input', triggerCalculation);
    if (ageInput) ageInput.addEventListener('input', triggerCalculation);

    if (applyBtn) {
        applyBtn.addEventListener('click', function (e) {
            e.preventDefault();
            if (currentSuggestedPrice > 0) {
                priceInput.value = currentSuggestedPrice;
                // Highlight input briefly
                priceInput.classList.add('is-valid');
                setTimeout(() => priceInput.classList.remove('is-valid'), 1500);
            }
        });
    }

    // Trigger on initial page load if values exist
    if (categorySelect.value) {
        fetchSmartPrice();
    }
});

// Search functionality - Filter customer cards on dashboard
document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.getElementById('searchInput');
    const customerCardsGrid = document.getElementById('customerCardsGrid');

    if (searchInput && customerCardsGrid) {
        let debounceTimer;
        let emptyStateElement = null;

        // Initially hide cards with customer-card-hidden class
        const hiddenCards = customerCardsGrid.querySelectorAll('.customer-card-hidden');
        hiddenCards.forEach(card => {
            card.style.display = 'none';
        });

        searchInput.addEventListener('input', function() {
            clearTimeout(debounceTimer);
            const query = this.value.trim().toLowerCase();

            debounceTimer = setTimeout(() => {
                const cards = customerCardsGrid.querySelectorAll('.profile-card');
                let visibleCount = 0;
                const showingAll = window.showingAllCustomers || false;

                cards.forEach(card => {
                    const customerName = card.getAttribute('data-customer-name') || '';
                    const customerPhone = card.getAttribute('data-customer-phone') || '';
                    
                    // Check if card was originally hidden (not in recent 4)
                    // Store this in a data attribute on first run
                    if (!card.hasAttribute('data-originally-hidden')) {
                        const wasHidden = card.classList.contains('customer-card-hidden');
                        card.setAttribute('data-originally-hidden', wasHidden ? 'true' : 'false');
                    }
                    const wasOriginallyHidden = card.getAttribute('data-originally-hidden') === 'true';
                    
                    if (query.length === 0) {
                        // When search is empty, respect the "Show All" toggle state
                        if (showingAll) {
                            // Show all customers - remove hidden class
                            card.classList.remove('customer-card-hidden');
                            card.style.display = '';
                            visibleCount++;
                        } else {
                            // Show only recent customers (recent 4)
                            if (wasOriginallyHidden) {
                                card.classList.add('customer-card-hidden');
                                card.style.display = 'none';
                            } else {
                                card.classList.remove('customer-card-hidden');
                                card.style.display = '';
                                visibleCount++;
                            }
                        }
                    } else {
                        // When searching, ALWAYS show all matching customers (even if not in recent 4)
                        const matches = customerName.includes(query) || customerPhone.includes(query);
                        if (matches) {
                            // Force show the card - remove hidden class temporarily
                            card.classList.remove('customer-card-hidden');
                            card.style.display = '';
                            visibleCount++;
                        } else {
                            // Hide non-matching cards
                            card.style.display = 'none';
                        }
                    }
                });

                // Show/hide empty state if needed
                if (visibleCount === 0 && query.length > 0) {
                    // Create or show empty state
                    if (!emptyStateElement) {
                        emptyStateElement = document.createElement('div');
                        emptyStateElement.className = 'empty-state';
                        emptyStateElement.style.textAlign = 'center';
                        emptyStateElement.style.padding = '3rem 1rem';
                        emptyStateElement.style.color = '#64748b';
                        customerCardsGrid.parentNode.insertBefore(emptyStateElement, customerCardsGrid.nextSibling);
                    }
                    emptyStateElement.innerHTML = `
                        <i data-lucide="search-x" style="width: 48px; height: 48px; opacity: 0.3; margin-bottom: 1rem;"></i>
                        <p style="margin: 0; font-size: 1rem;">No customers found matching "${query}"</p>
                    `;
                    emptyStateElement.style.display = 'block';
                    if (typeof lucide !== 'undefined') {
                        lucide.createIcons();
                    }
                } else {
                    // Hide empty state
                    if (emptyStateElement) {
                        emptyStateElement.style.display = 'none';
                    }
                }
            }, 150);
        });
    }
});

// Add debt item functionality
let itemCount = 0;

function addItem() {
    const container = document.getElementById('itemsContainer');
    const products = window.productsData || [];

    const itemHtml = `
        <div class="item-row" id="item-${itemCount}">
            <div style="display: flex; flex-direction: column; gap: 0.5rem; flex: 1;">
                <select onchange="selectProduct(${itemCount}, this.value)" class="form-control" id="select-${itemCount}">
                    <option value="">-- Select Product --</option>
                    ${products.map(p => `<option value="${p.id}" data-price="${p.price}">${p.name} - $${parseFloat(p.price).toFixed(2)}</option>`).join('')}
                </select>
                <input type="text" name="product_name_${itemCount}" placeholder="Or type custom product name" class="form-control" id="custom-name-${itemCount}" oninput="handleCustomNameInput(${itemCount})">
            </div>
            <input type="number" name="price_${itemCount}" placeholder="$ Price" step="0.01" min="0" class="form-control" id="price-${itemCount}">
            <input type="number" name="quantity_${itemCount}" value="1" min="1" class="form-control">
            <button type="button" class="remove-item" onclick="removeItem(${itemCount})">
                <i data-lucide="x" style="width: 16px; height: 16px;"></i>
            </button>
        </div>
    `;

    container.insertAdjacentHTML('beforeend', itemHtml);
    itemCount++;

    // Reinitialize lucide icons for new content
    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }
}

function selectProduct(index, value) {
    const customNameInput = document.getElementById(`custom-name-${index}`);
    const priceInput = document.getElementById(`price-${index}`);
    const select = document.getElementById(`select-${index}`);

    if (value) {
        // Product selected from dropdown
        const selectedOption = select.options[select.selectedIndex];
        const price = selectedOption.dataset.price;
        const name = selectedOption.text.split(' - $')[0];

        // Clear custom name input when product is selected
        customNameInput.value = '';
        customNameInput.required = false;
        
        // Set the product name in hidden field (will be used on submit)
        customNameInput.setAttribute('data-selected-name', name);
        priceInput.value = price;
    } else {
        // Nothing selected - clear everything
        customNameInput.value = '';
        customNameInput.removeAttribute('data-selected-name');
        customNameInput.required = false;
        priceInput.value = '';
    }
}

function handleCustomNameInput(index) {
    const customNameInput = document.getElementById(`custom-name-${index}`);
    const select = document.getElementById(`select-${index}`);
    
    // If user types in custom name, clear the select dropdown
    if (customNameInput.value.trim()) {
        select.value = '';
        customNameInput.removeAttribute('data-selected-name');
        customNameInput.required = true;
    } else {
        customNameInput.required = false;
    }
}

function removeItem(index) {
    const item = document.getElementById(`item-${index}`);
    if (item) {
        item.remove();
    }
}

// Form validation before submit
function validateDebtForm() {
    const items = document.querySelectorAll('.item-row');
    let hasValidItem = false;

    items.forEach(item => {
        const nameInput = item.querySelector('input[name^="product_name"]');
        const priceInput = item.querySelector('input[name^="price"]');
        const select = item.querySelector('select');

        // If product is selected from dropdown, use that name
        if (select && select.value) {
            const selectedOption = select.options[select.selectedIndex];
            const name = selectedOption.text.split(' - $')[0];
            nameInput.value = name;
        }
        // Otherwise, use the custom name input value (if user typed something)

        if (nameInput.value && nameInput.value.trim() && priceInput.value) {
            hasValidItem = true;
        }
    });

    if (!hasValidItem) {
        alert('Please add at least one item with a name and price.');
        return false;
    }

    return true;
}

// Modal functionality
function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.add('active');
        // Reinitialize lucide icons for modal content
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    }
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.remove('active');
    }
}

// Close modal when clicking outside
document.addEventListener('click', function(e) {
    if (e.target.classList.contains('modal-overlay')) {
        e.target.classList.remove('active');
    }
});

// Confirm delete
function confirmDelete(message) {
    return confirm(message || 'Are you sure you want to delete this?');
}

// Format currency
function formatCurrency(amount) {
    return '$' + parseFloat(amount).toFixed(2);
}

// Initialize item on page load if on customer detail page
document.addEventListener('DOMContentLoaded', function() {
    const itemsContainer = document.getElementById('itemsContainer');
    if (itemsContainer && itemsContainer.children.length === 0) {
        addItem();
    }
});

// Profile card dropdown menu
function toggleProfileMenu(button) {
    const dropdown = button.nextElementSibling;
    const isOpen = dropdown.classList.contains('show');

    // Close all other dropdowns first
    document.querySelectorAll('.profile-dropdown.show').forEach(d => {
        d.classList.remove('show');
    });

    // Toggle this dropdown
    if (!isOpen) {
        dropdown.classList.add('show');
    }
}

// Close profile dropdowns when clicking outside
document.addEventListener('click', function(e) {
    if (!e.target.closest('.profile-card-menu')) {
        document.querySelectorAll('.profile-dropdown.show').forEach(d => {
            d.classList.remove('show');
        });
    }
});

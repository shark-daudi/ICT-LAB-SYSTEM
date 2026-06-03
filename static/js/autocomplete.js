function initAutocomplete(inputElement, fetchUrl, valueKey = 'serial') {
    let timeout = null;
    const datalistId = inputElement.getAttribute('list') || 'autocomplete-list';
    let datalist = document.getElementById(datalistId);
    if (!datalist) {
        datalist = document.createElement('datalist');
        datalist.id = datalistId;
        inputElement.setAttribute('list', datalistId);
        inputElement.parentNode.appendChild(datalist);
    }
    inputElement.addEventListener('input', () => {
        clearTimeout(timeout);
        const q = inputElement.value.trim();
        if (q.length < 2) return;
        timeout = setTimeout(async () => {
            try {
                const res = await fetch(`${fetchUrl}?q=${encodeURIComponent(q)}`);
                const items = await res.json();
                datalist.innerHTML = '';
                items.forEach(item => {
                    const opt = document.createElement('option');
                    opt.value = item[valueKey];
                    datalist.appendChild(opt);
                });
            } catch (err) { console.error('Autocomplete error', err); }
        }, 300);
    });
}
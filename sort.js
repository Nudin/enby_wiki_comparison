document.addEventListener('DOMContentLoaded', () => {
    const table = document.querySelector("table");
    const filterCheckbox = document.getElementById('filterCheckbox');

    // Sorting functionality
    table.querySelectorAll('th').forEach((header, index) => {
        header.addEventListener('click', () => sortTable(index, header));
    });

    function sortTable(colIndex, header) {
        console.log("sort")
        const tbody = table.querySelector('tbody');
        const rows = Array.from(tbody.rows);

        const isAscending = header.classList.contains('sorted-asc');
        const direction = isAscending ? -1 : 1;

        // Clear previous sorting classes
        table.querySelectorAll('th').forEach(th => th.classList.remove('sorted-asc', 'sorted-desc'));

        // Sort rows
        rows.sort((a, b) => {
            const cellA = a.cells[colIndex].textContent.trim();
            const cellB = b.cells[colIndex].textContent.trim();

            const aValue = isNaN(cellA) ? cellA.toLowerCase() : parseFloat(cellA);
            const bValue = isNaN(cellB) ? cellB.toLowerCase() : parseFloat(cellB);

            if (aValue > bValue) return direction;
            if (aValue < bValue) return -direction;
            return 0;
        });

        // Append sorted rows back to tbody
        rows.forEach(row => tbody.appendChild(row));

        // Update header class
        header.classList.add(isAscending ? 'sorted-desc' : 'sorted-asc');
    }

    // Filtering functionality
    filterCheckbox.addEventListener('change', () => {
        const tbody = table.querySelector('tbody');
        const rows = Array.from(tbody.rows);

        rows.forEach(row => {
            if (filterCheckbox.checked) {
                row.classList.toggle('hidden', !row.classList.contains('error'));
            } else {
                row.classList.remove('hidden');
            }
        });
    });
});

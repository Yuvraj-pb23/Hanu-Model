// India State Map Popup Enhancement
document.addEventListener('DOMContentLoaded', function () {
	const stateCards = document.querySelectorAll('.state-card[data-map]');
	const indiaMapDisplay = document.getElementById('indiaMapDisplay');
	const indiaBaseMap = document.getElementById('indiaBaseMap');
	if (!stateCards.length || !indiaMapDisplay || !indiaBaseMap) return;

	stateCards.forEach(card => {
		card.addEventListener('mouseenter', function () {
			const mapSrc = card.getAttribute('data-map');
			if (!mapSrc) return;
			indiaMapDisplay.src = mapSrc;
			indiaMapDisplay.classList.add('state-active');
			indiaBaseMap.classList.add('base-map-hidden');
		});
		card.addEventListener('mouseleave', function () {
			indiaMapDisplay.classList.remove('state-active');
			indiaBaseMap.classList.remove('base-map-hidden');
		});
	});
});


/* --------------------------------------------------
   LOCOMOTIVE SCROLL & GALLERY INITIALIZATION
-------------------------------------------------- */
let locoScroll;

document.addEventListener("DOMContentLoaded", () => {
  console.log("DOM loaded, initializing gallery...");
  
  // Initialize Locomotive Scroll safely
  const scrollContainer = document.querySelector("[data-scroll-container]");
  if (scrollContainer && typeof LocomotiveScroll !== 'undefined') {
    try {
      locoScroll = new LocomotiveScroll({
        el: scrollContainer,
        smooth: true,
        multiplier: 1.1,
        lerp: 0.08,
      });
      console.log("Locomotive Scroll initialized");
    } catch (e) {
      console.warn("Locomotive Scroll failed to initialize:", e);
    }
  } else {
    console.warn("Locomotive Scroll not available or container not found");
  }

  /* --------------------------------------------------
     LOAD IMAGES FROM DJANGO TEMPLATE
  -------------------------------------------------- */
  const imageElements = document.querySelectorAll("#imageData [data-image]");
  console.log("Image elements found:", imageElements.length);
  
  const images = Array.from(imageElements).map((el) => ({
    url: el.getAttribute("data-image"),
    name: el.getAttribute("data-name"),
  }));
  
  console.log("Images loaded:", images.length);
  if (images.length > 0) {
    console.log("First image URL:", images[0].url);
  }

  if (images.length === 0) {
    console.error("No images found in #imageData");
    const container = document.getElementById("galleryContainer");
    if (container) {
      container.innerHTML =
        '<div class="text-gray-400 flex items-center justify-center h-full text-xl">No images found.</div>';
    }
    return;
  }

  const container = document.getElementById("galleryContainer");
  const grid = document.getElementById("infiniteGrid");

  let isDragging = false;
  let hasMoved = false;

  let startX = 0,
    startY = 0;

  let currentX = 0,
    currentY = 0;

  let targetX = 0,
    targetY = 0;

  let velocityX = 0,
    velocityY = 0;

  let lastMoveTime = Date.now();

  const cardSize = 280;
  const gap = 64;
  const cellSize = cardSize + gap;
  const cols = 50;
  const rows = 50;

  grid.style.gridTemplateColumns = `repeat(${cols}, ${cardSize}px)`;

  const totalWidth = cols * cellSize;
  const totalHeight = rows * cellSize;

  currentX = targetX =
    -(totalWidth / 2) + container.clientWidth / 2;
  currentY = targetY =
    -(totalHeight / 2) + container.clientHeight / 2;

  const fragment = document.createDocumentFragment();
  let index = 0;
  const totalCards = cols * rows;

  for (let i = 0; i < totalCards; i++) {
    const card = document.createElement("div");
    card.className = "gallery-card";
    const currentIndex = index;
    card.dataset.imageIndex = currentIndex;

    const inner = document.createElement("div");
    inner.className = "gallery-card-inner";

    const img = document.createElement("img");
    img.src = images[currentIndex].url;
    img.alt = images[currentIndex].name;

    const blur = document.createElement("div");
    blur.style.cssText =
      "position:absolute;width:14rem;height:12rem;background:white;filter:blur(50px);left:-50%;top:-50%;opacity:0.3;pointer-events:none";

    inner.appendChild(img);
    card.appendChild(inner);
    card.appendChild(blur);

    card.addEventListener("click", () => {
      if (!hasMoved) openModal(event, images[currentIndex].url, card);
    });

    fragment.appendChild(card);
    index = (index + 1) % images.length;
  }

  grid.appendChild(fragment);

  /* ===========================================================
       UPDATE POSITION
  ============================================================ */
  function updatePosition() {
    grid.style.transform = `translate3d(${currentX}px, ${currentY}px, 0)`;
  }

  /* ===========================================================
       DRAGGING WITH REAL-TIME MOMENTUM
  ============================================================ */
  container.addEventListener("mousedown", startDrag);
  container.addEventListener("touchstart", startDrag, { passive: false });

  function startDrag(e) {
    const p = e.touches ? e.touches[0] : e;

    isDragging = true;
    hasMoved = false;

    startX = p.clientX - targetX;
    startY = p.clientY - targetY;

    lastMoveTime = Date.now();

    document.addEventListener("mousemove", onDrag);
    document.addEventListener("touchmove", onDrag, { passive: false });
    document.addEventListener("mouseup", stopDrag);
    document.addEventListener("touchend", stopDrag);
  }

  function onDrag(e) {
    e.preventDefault();

    const p = e.touches ? e.touches[0] : e;

    const now = Date.now();
    const dt = now - lastMoveTime;

    const newTargetX = p.clientX - startX;
    const newTargetY = p.clientY - startY;

    velocityX = (newTargetX - targetX) / dt;
    velocityY = (newTargetY - targetY) / dt;

    targetX = newTargetX;
    targetY = newTargetY;

    hasMoved = true;
    lastMoveTime = now;
  }

  function stopDrag() {
    isDragging = false;

    document.removeEventListener("mousemove", onDrag);
    document.removeEventListener("touchmove", onDrag);
    document.removeEventListener("mouseup", stopDrag);
    document.removeEventListener("touchend", stopDrag);
  }

  /* ===========================================================
       ANIMATION LOOP — MOMENTUM + SMOOTH DRAGGING
  ============================================================ */
  function animate() {
    if (isDragging) {
      // Ease grid position toward mouse
      currentX += (targetX - currentX) * 0.25;
      currentY += (targetY - currentY) * 0.25;
    } else {
      // Continue drifting using momentum
      targetX += velocityX * 30;
      targetY += velocityY * 30;

      // Friction
      velocityX *= 0.35;
      velocityY *= 0.35;

      // Ease into position
      currentX += (targetX - currentX) * 0.1;
      currentY += (targetY - currentY) * 0.1;
    }

    updatePosition();
    requestAnimationFrame(animate);
  }

  animate();

  /* UPDATE LOCO SCROLL */
  setTimeout(() => {
    if (locoScroll) locoScroll.update();
  }, 300);

  /* ===========================================================
       MODAL FUNCTIONS
  =========================================================== */
  let clickedCard = null;

  function openModal(event, src, card) {
    clickedCard = card;

    const modal = document.getElementById("galleryModal");
    const modalImage = document.getElementById("modalImage");

    modalImage.src = src;
    modal.style.display = "flex";

    requestAnimationFrame(() => modal.classList.add("active"));
    document.body.style.overflow = "hidden";
  }

  function closeModal() {
    const modal = document.getElementById("galleryModal");

    modal.classList.remove("active");

    setTimeout(() => {
      modal.style.display = "none";
      document.body.style.overflow = "auto";
    }, 400);
  }

  // Expose closeModal globally for HTML onclick
  window.closeModal = closeModal;

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeModal();
  });

  // Update Locomotive Scroll after everything loads
  window.addEventListener("load", () => {
    setTimeout(() => {
      if (locoScroll) locoScroll.update();
    }, 500);
  });
});

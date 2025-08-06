// frontend/src/js/detail.js (ecommerce1)
const BASE_URL = "http://127.0.0.1:8001";

// SIZE_TABLE as specified in requirements
const SIZE_TABLE = {
  ayakkabi: ["37","38","39","40","41","42"],
  tshirt:  ["XS","S","M","L","XL"],
  sweat:   ["S","M","L","XL"],
  sapka:   ["Standart"]
};

const params = new URLSearchParams(window.location.search);
const productId = params.get("id");
const catKey = params.get("cat"); // ayakkabi, tshirt, ...

let currentProduct = null;
let currentImages = [];
let currentImageIndex = 0;
let allComments = [];
let visibleCommentsCount = 6;

// ---------- API ----------
async function fetchProduct(cat, id) {
  const res = await fetch(`${BASE_URL}/products/${cat}`);
  const data = await res.json();
  return data.find(p => p.id === id) || null;
}

async function fetchComments(cat, id) {
  const res = await fetch(`${BASE_URL}/comments/${cat}`);
  const all = await res.json();
  return all[id] || [];
}

// rating summary: { avg, total, counts: {"1":n,"2":n,"3":n,"4":n,"5":n} }
async function fetchRatingSummary(cat, id) {
  const res = await fetch(`${BASE_URL}/rating-summary/${cat}/${id}`);
  if (!res.ok) return null;
  return res.json();
}

// ---------- UI helpers ----------
function ensureBreakdownStyles() {
  if (document.getElementById("rb-styles")) return;
  const css = `
    .rating-breakdown{margin-top:.5rem}
    .rb-row{display:flex;align-items:center;gap:.5rem;margin:.25rem 0}
    .rb-star{width:2.2rem;color:#ffc107;font-weight:600;text-align:right}
    .rb-bar{flex:1;height:8px;background:#eee;border-radius:6px;overflow:hidden}
    .rb-bar > span{display:block;height:100%;background:#ffc107}
    .rb-count{width:2.2rem;text-align:left;color:#555;font-weight:600}
  `;
  const style = document.createElement("style");
  style.id = "rb-styles";
  style.textContent = css;
  document.head.appendChild(style);
}

function createBreakdown(summary) {
  ensureBreakdownStyles();
  if (!summary || !summary.counts) return "";
  const total = summary.total || 0;
  const counts = summary.counts || {};
  const rows = [5,4,3,2,1].map(star => {
    const c = counts[String(star)] || 0;
    const pct = total ? Math.round((c / total) * 100) : 0;
    return `
      <div class="rb-row">
        <span class="rb-star">${star}★</span>
        <div class="rb-bar"><span style="width:${pct}%"></span></div>
        <span class="rb-count">${c}</span>
      </div>
    `;
  }).join("");
  return `<div class="rating-breakdown">${rows}</div>`;
}

function createImageGallery(product) {
  const images = product.images || [];
  const cacheBuster = new Date().getTime(); 
  currentImages = images.map(img => `${BASE_URL}/${img}?v=${cacheBuster}`);
  if (currentImages.length === 0) return '<p>Görsel bulunamadı</p>';

  const mainImageHtml = `
    <div class="main-image-container">
      <img id="main-image" src="${currentImages[0]}" alt="${product.name}" class="main-image" onclick="openLightbox(0)">
    </div>
  `;

  const thumbnailsHtml = currentImages.length > 1 ? `
    <div class="thumbnail-strip">
      ${currentImages.map((src, index) => `
        <img src="${src}" alt="${product.name}" class="thumbnail ${index === 0 ? 'active' : ''}" onclick="changeMainImage(${index})">
      `).join('')}
    </div>
  ` : '';

  return `
    <div class="image-gallery">
      ${mainImageHtml}
      ${thumbnailsHtml}
    </div>
  `;
}

function changeMainImage(index) {
  const mainImage = document.getElementById("main-image");
  mainImage.src = currentImages[index];
  currentImageIndex = index;
  document.querySelectorAll('.thumbnail').forEach((thumb, i) => {
    thumb.classList.toggle('active', i === index);
  });
}

function openLightbox(index) {
  currentImageIndex = index;
  const modal = document.getElementById("lightbox-modal");
  const lightboxImage = document.getElementById("lightbox-image");
  lightboxImage.src = currentImages[index];
  modal.style.display = "flex";
  document.body.style.overflow = "hidden";
}
function closeLightbox() {
  document.getElementById("lightbox-modal").style.display = "none";
  document.body.style.overflow = "auto";
}
function nextImage() {
  if (currentImages.length <= 1) return;
  currentImageIndex = (currentImageIndex + 1) % currentImages.length;
  document.getElementById("lightbox-image").src = currentImages[currentImageIndex];
}
function prevImage() {
  if (currentImages.length <= 1) return;
  currentImageIndex = currentImageIndex === 0 ? currentImages.length - 1 : currentImageIndex - 1;
  document.getElementById("lightbox-image").src = currentImages[currentImageIndex];
}

// Close lightbox on outside click / Esc / Arrows
document.addEventListener('click', (e) => {
  const modal = document.getElementById("lightbox-modal");
  if (e.target === modal) closeLightbox();
});
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') closeLightbox();
  if (e.key === 'ArrowRight') nextImage();
  if (e.key === 'ArrowLeft') prevImage();
});

function createSizeSelection(product) {
  if (!product.stock || !Array.isArray(product.stock) || product.stock.length === 0) {
    return '<div class="size-selection"><span class="info-label">Beden Bilgisi</span><p>Beden bilgisi mevcut değil</p></div>';
  }

  const sizeOptionsHtml = product.stock.map(item => {
    const isAvailable = item.isAvailable;
    return isAvailable
      ? `<div class="size-option" onclick="selectSize(this, '${item.size}')">${item.size}</div>`
      : `<div class="size-option is-out"><span>${item.size}</span><button class="notify-btn" onclick="showNotifyPopup('${product.id}', '${item.size}')">Haber Ver</button></div>`;
  }).join('');

  return `
    <div class="size-selection">
      <span class="info-label">Beden Seçimi</span>
      <div class="size-options">
        ${sizeOptionsHtml}
      </div>
    </div>
  `;
}

function selectSize(element, size) {
  document.querySelectorAll('.size-option.selected').forEach(option => {
    option.classList.remove('selected');
  });
  element.classList.add('selected');
  const addToCartBtn = document.getElementById('add-to-cart-btn');
  if (addToCartBtn) addToCartBtn.disabled = false;
}

// ---- comments ----
function renderComments(comments) {
  // sadece yazılı yorumları göster
  const onlyText = comments.filter(c => (c.text ?? "").trim().length > 0);

  if (onlyText.length === 0) {
    return `
      <div class="comments-section">
        <div class="comments-header">
          <h3>Yorumlar</h3>
          <span class="comments-count">0</span>
        </div>
        <p>Henüz yorum yapılmamış. İlk yorumu siz yapın!</p>
      </div>
    `;
  }

  const visibleComments = onlyText.slice(0, visibleCommentsCount);
  const hasMoreComments = onlyText.length > visibleCommentsCount;

  const commentsHtml = visibleComments.map(comment => `
    <li class="comment-item">
      <div class="comment-header">
        <span class="comment-user">${comment.user}</span>
        <span class="comment-rating">⭐ ${comment.rating}</span>
      </div>
      <p class="comment-text">${comment.text}</p>
    </li>
  `).join('');

  const showMoreButton = hasMoreComments ? `
    <button class="show-more-comments" onclick="showMoreComments()">
      Daha Fazla Göster (${onlyText.length - visibleCommentsCount} yorum daha)
    </button>
  ` : '';

  return `
    <div class="comments-section">
      <div class="comments-header">
        <h3>Yorumlar</h3>
        <span class="comments-count">${onlyText.length}</span>
      </div>
      <ul>
        ${commentsHtml}
      </ul>
      ${showMoreButton}
    </div>
  `;
}

function showMoreComments() {
  visibleCommentsCount += 6;
  const commentsContainer = document.getElementById("comments-container");
  commentsContainer.innerHTML = renderComments(allComments);
}

// ---------- page render ----------
async function renderProductDetail() {
  const detailContainer = document.getElementById("product-detail-container");
  const commentsContainer = document.getElementById("comments-container");

  if (!productId || !catKey) {
    detailContainer.innerHTML = "<p>Eksik parametre.</p>";
    return;
  }

  try {
    const [product, comments, summary] = await Promise.all([
      fetchProduct(catKey, productId),
      fetchComments(catKey, productId),
      fetchRatingSummary(catKey, productId)
    ]);

    currentProduct = product;
    allComments = comments;

    if (!product) {
      detailContainer.innerHTML = "<p>Ürün bulunamadı.</p>";
      return;
    }

    document.title = `${product.name} - Ürün Detayı`;

    const avg = summary?.avg ?? product.rating ?? 0;
    const avgRounded = Math.round(avg * 10) / 10;
    const ratingStars = '⭐'.repeat(Math.floor(avg)) + (avg % 1 >= 0.5 ? '⭐' : '');

    detailContainer.innerHTML = `
      <div class="product-detail-layout">
        <div class="product-images">
          ${createImageGallery(product)}
        </div>
        
        <div class="product-info">
          <h2>${product.name}</h2>
          <div class="price">${product.price} TL</div>
          
          <div class="rating-info">
            <span class="rating-stars">${ratingStars} ${avgRounded.toFixed(1)}</span>
            <span class="rating-count">(${summary?.total ?? comments.length} değerlendirme)</span>
          </div>

          ${createBreakdown(summary)}

          <div class="info-section">
            <span class="info-label">Kategori</span>
            <p>${product.category}</p>
          </div>

          ${createSizeSelection(product)}

          <div class="info-section">
            <span class="info-label">Ürün Açıklaması</span>
            <p>${product.description}</p>
          </div>

          <button id="add-to-cart-btn" class="add-to-cart" disabled onclick="addToCart()">
            Sepete Ekle
          </button>
        </div>
      </div>
    `;

    commentsContainer.innerHTML = renderComments(comments);

  } catch (error) {
    console.error("Ürün detayı yüklenirken hata:", error);
    detailContainer.innerHTML = "<p>Ürün detayı yüklenemedi.</p>";
  }
}

function addToCart() {
  const button = document.getElementById('add-to-cart-btn');
  const originalText = button.textContent;
  button.textContent = 'Sepete Eklendi!';
  button.style.backgroundColor = '#28a745';
  setTimeout(() => {
    button.textContent = originalText;
    button.style.backgroundColor = '';
  }, 2000);
}

function showNotifyPopup(productId, size) {
  alert(`"${productId}" kodlu ürünün "${size}" bedeni stoklarımıza girdiğinde e-posta ile bilgilendirileceksiniz.\n\n(Bu bir demo özelliğidir.)`);
}

window.addEventListener("DOMContentLoaded", renderProductDetail);

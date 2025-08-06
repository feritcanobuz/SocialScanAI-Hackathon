// frontend/src/js/detail.js (ecommerce3 - NeonGrid)
// Gerçek ortalama & dağılım: /rating-summary/{cat}/{id}

const BASE_URL = "http://127.0.0.1:8003";

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

// -------- Helpers (rating & stars) --------
function starsFromAverage(avg) {
  const full = Math.floor(avg || 0);
  const half = ((avg || 0) % 1) >= 0.5 ? 1 : 0;
  return "⭐".repeat(full + half);
}

function calcStatsFromComments(arr) {
  const counts = { "1":0, "2":0, "3":0, "4":0, "5":0 };
  let total = 0, sum = 0;
  for (const c of (arr || [])) {
    const r = Number(c?.rating);
    if (Number.isFinite(r) && r >= 1 && r <= 5) {
      total += 1; sum += r; counts[String(Math.round(r))] += 1;
    }
  }
  return { avg: total ? (sum/total) : 0, total, counts };
}

function renderDistribution(counts, total) {
  const order = ["5","4","3","2","1"];
  const rows = order.map(k => {
    const cnt = counts?.[k] || 0;
    const pct = total ? Math.round((cnt/total)*100) : 0;
    return `
      <div class="dist-row">
        <div class="dist-starlabel">${k}★</div>
        <div class="dist-bar"><div class="dist-bar-fill" style="width:${pct}%"></div></div>
        <div class="dist-count">${cnt}</div>
      </div>
    `;
  }).join("");
  return `
    <div class="rating-distribution">
      <div class="dist-title">Yıldız Dağılımı</div>
      ${rows}
    </div>
  `;
}

// -------- API --------
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

async function fetchRatingSummary(cat, id) {
  const res = await fetch(`${BASE_URL}/rating-summary/${cat}/${id}`);
  if (!res.ok) return null;
  return res.json(); // { avg, total, counts }
}

// -------- Gallery --------
function createImageGallery(product) {
  const images = product.images || [];
  const cacheBuster = Date.now();
  currentImages = images.map(img => `${BASE_URL}/${img}?v=${cacheBuster}`);
  if (currentImages.length === 0) return '<p>Görsel bulunamadı</p>';

  const mainImageHtml = `
    <div class="main-image-container">
      <img id="main-image" src="${currentImages[0]}" alt="${product.name}"
           class="main-image" onclick="openLightbox(0)">
    </div>
  `;
  const thumbnailsHtml = currentImages.length > 1 ? `
    <div class="thumbnail-strip">
      ${currentImages.map((src, index) => `
        <img src="${src}" alt="${product.name}"
             class="thumbnail ${index === 0 ? 'active' : ''}"
             onclick="changeMainImage(${index})">
      `).join('')}
    </div>
  ` : '';

  return `<div class="image-gallery">${mainImageHtml}${thumbnailsHtml}</div>`;
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
document.addEventListener('click', e => {
  const modal = document.getElementById("lightbox-modal");
  if (e.target === modal) closeLightbox();
});
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeLightbox();
  if (e.key === 'ArrowRight') nextImage();
  if (e.key === 'ArrowLeft')  prevImage();
});

// -------- Size selection --------
function createSizeSelection(product) {
  if (!product.stock || !Array.isArray(product.stock) || product.stock.length === 0) {
    return '<div class="size-selection"><span class="info-label">Beden Bilgisi</span><p>Beden bilgisi mevcut değil</p></div>';
  }
  const sizeOptionsHtml = product.stock.map(item => {
    const isAvailable = item.isAvailable;
    if (isAvailable) {
      return `<div class="size-option" onclick="selectSize(this, '${item.size}')">${item.size}</div>`;
    }
    return `
      <div class="size-option is-out">
        <span>${item.size}</span>
        <button class="notify-btn" onclick="showNotifyPopup('${product.id}', '${item.size}')">Haber Ver</button>
      </div>
    `;
  }).join('');
  return `
    <div class="size-selection">
      <span class="info-label">Beden Seçimi</span>
      <div class="size-options">${sizeOptionsHtml}</div>
    </div>
  `;
}
function selectSize(element, size) {
  document.querySelectorAll('.size-option.selected').forEach(option => option.classList.remove('selected'));
  element.classList.add('selected');
  const addToCartBtn = document.getElementById('add-to-cart-btn');
  if (addToCartBtn) addToCartBtn.disabled = false;
}

// -------- Comments (only those with text) --------
function renderComments(comments) {
  // Sadece text’i olan yorumları göster
  const readable = (comments || []).filter(c => {
    const hasText = typeof c.text === "string" && c.text.trim().length > 0;
    const r = Number(c?.rating);
    return hasText && Number.isFinite(r) && r >= 1 && r <= 5;
  });

  if (readable.length === 0) {
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

  const visible = readable.slice(0, visibleCommentsCount);
  const hasMore = readable.length > visibleCommentsCount;

  const commentsHtml = visible.map(comment => `
    <li class="comment-item">
      <div class="comment-header">
        <span class="comment-user">${comment.user}</span>
        <span class="comment-rating">⭐ ${comment.rating}</span>
      </div>
      <p class="comment-text">${comment.text}</p>
    </li>
  `).join('');

  const showMoreButton = hasMore ? `
    <button class="show-more-comments" onclick="showMoreComments()">
      Daha Fazla Göster (${readable.length - visibleCommentsCount} yorum daha)
    </button>
  ` : '';

  return `
    <div class="comments-section">
      <div class="comments-header">
        <h3>Yorumlar</h3>
        <span class="comments-count">${readable.length}</span>
      </div>
      <ul>${commentsHtml}</ul>
      ${showMoreButton}
    </div>
  `;
}
function showMoreComments() {
  visibleCommentsCount += 6;
  const commentsContainer = document.getElementById("comments-container");
  commentsContainer.innerHTML = renderComments(allComments);
}

// -------- Page render --------
async function renderProductDetail() {
  const detailContainer = document.getElementById("product-detail-container");
  const commentsContainer = document.getElementById("comments-container");

  if (!productId || !catKey) {
    detailContainer.innerHTML = "<p>Eksik parametre.</p>";
    return;
  }

  try {
    const [product, comments, summaryResp] = await Promise.all([
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

    // Özet (backend), yoksa yorumlardan hesapla
    const summary = summaryResp || calcStatsFromComments(comments);
    const avg = summary.avg || 0;
    const total = summary.total || 0;
    const counts = summary.counts || { "1":0, "2":0, "3":0, "4":0, "5":0 };
    const ratingStars = `${starsFromAverage(avg)} ${avg.toFixed(1)}`;

    document.title = `${product.name} - Ürün Detayı`;

    detailContainer.innerHTML = `
      <div class="product-detail-layout">
        <div class="product-images">
          ${createImageGallery(product)}
        </div>

        <div class="product-info">
          <h2>${product.name}</h2>
          <div class="price">${product.price} TL</div>

          <div class="rating-info">
            <span class="rating-stars">${ratingStars}</span>
            <span class="rating-count">(${total} değerlendirme)</span>
          </div>

          ${renderDistribution(counts, total)}

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

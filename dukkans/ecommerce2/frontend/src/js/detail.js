// frontend/src/js/detail.js
const BASE_URL = "http://127.0.0.1:8002";

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
  return await res.json(); // {avg,total,counts}
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
  const modal = document.getElementById("lightbox-modal");
  modal.style.display = "none";
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
document.addEventListener('click', e => { const m = document.getElementById("lightbox-modal"); if (e.target === m) closeLightbox(); });
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeLightbox(); if (e.key === 'ArrowRight') nextImage(); if (e.key === 'ArrowLeft') prevImage(); });

function createSizeSelection(product) {
  if (!product.stock || !Array.isArray(product.stock) || product.stock.length === 0) {
    return '<div class="size-selection"><span class="info-label">Beden Bilgisi</span><p>Beden bilgisi mevcut değil</p></div>';
  }
  const sizeOptionsHtml = product.stock.map(item => {
    if (item.isAvailable) {
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

function selectSize(el) {
  document.querySelectorAll('.size-option.selected').forEach(o => o.classList.remove('selected'));
  el.classList.add('selected');
  const btn = document.getElementById('add-to-cart-btn');
  if (btn) btn.disabled = false;
}

function renderRatingBars(counts, total) {
  if (!total) return "";
  const order = ["5","4","3","2","1"];
  return `
    <div class="rating-bars">
      ${order.map(star => {
        const c = counts?.[star] || 0;
        const pct = Math.round((c / total) * 100);
        return `
          <div class="rating-bar-row" style="display:flex;align-items:center;gap:.5rem;margin:.2rem 0">
            <span style="min-width:18px">${star}</span>
            <div style="flex:1;height:8px;background:#eee;border-radius:6px;overflow:hidden">
              <div style="width:${pct}%;height:100%;background:#ffc107"></div>
            </div>
            <span style="min-width:34px;text-align:right">${c}</span>
          </div>
        `;
      }).join("")}
    </div>
  `;
}

function renderComments(comments) {
  // Sadece metni olan yorumları göster
  const filtered = (comments || []).filter(c => c.text && String(c.text).trim().length > 0);
  if (filtered.length === 0) {
    return `
      <div class="comments-section">
        <div class="comments-header">
          <h3>Yorumlar</h3>
          <span class="comments-count">0</span>
        </div>
        <p>Metin içeren yorum bulunamadı.</p>
      </div>
    `;
  }

  const visible = filtered.slice(0, visibleCommentsCount);
  const hasMore = filtered.length > visibleCommentsCount;

  const commentsHtml = visible.map(comment => `
    <li class="comment-item">
      <div class="comment-header">
        <span class="comment-user">${comment.user}</span>
        <span class="comment-rating">⭐ ${comment.rating}</span>
      </div>
      <p class="comment-text">${comment.text}</p>
    </li>
  `).join('');

  const moreBtn = hasMore
    ? `<button class="show-more-comments" onclick="showMoreComments()">Daha Fazla Göster (${filtered.length - visibleCommentsCount} yorum daha)</button>`
    : '';

  return `
    <div class="comments-section">
      <div class="comments-header">
        <h3>Yorumlar</h3>
        <span class="comments-count">${filtered.length}</span>
      </div>
      <ul>${commentsHtml}</ul>
      ${moreBtn}
    </div>
  `;
}

function showMoreComments() {
  visibleCommentsCount += 6;
  const commentsContainer = document.getElementById("comments-container");
  commentsContainer.innerHTML = renderComments(allComments);
}

async function renderProductDetail() {
  const detailContainer = document.getElementById("product-detail-container");
  const commentsContainer = document.getElementById("comments-container");

  if (!productId || !catKey) {
    detailContainer.innerHTML = "<p>Eksik parametre.</p>";
    return;
  }

  try {
    const [product, comments, rating] = await Promise.all([
      fetchProduct(catKey, productId),
      fetchComments(catKey, productId),
      fetchRatingSummary(catKey, productId),
    ]);

    currentProduct = product;
    allComments = comments;

    if (!product) {
      detailContainer.innerHTML = "<p>Ürün bulunamadı.</p>";
      return;
    }

    document.title = `${product.name} - Ürün Detayı`;

    const avg = rating?.avg ?? product.rating ?? 0;
    const totalVotes = rating?.total ?? comments.length ?? 0;
    const ratingStars = "⭐".repeat(Math.floor(avg)) + ((avg % 1) >= 0.5 ? "⭐" : "");

    detailContainer.innerHTML = `
      <div class="product-detail-layout">
        <div class="product-images">
          ${createImageGallery(product)}
        </div>

        <div class="product-info">
          <h2>${product.name}</h2>
          <div class="price">${product.price} TL</div>

          <div class="rating-info">
            <span class="rating-stars">${ratingStars} ${avg.toFixed(1)}</span>
            <span class="rating-count">(${totalVotes} değerlendirme)</span>
          </div>

          ${rating ? renderRatingBars(rating.counts, rating.total) : ""}

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

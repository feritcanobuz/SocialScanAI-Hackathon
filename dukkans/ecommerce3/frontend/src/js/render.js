// frontend/src/js/render.js (ecommerce3 - NeonGrid)
// Liste kartlarında GERÇEK ortalama: comments'tan hesaplanır

const BASE_URL = "http://127.0.0.1:8003";

let currentCat = "all";
let allProducts = [];
let ratingMap = {}; // { [productId]: { avg:number, total:number } }

// ---- Helpers: gerçek ortalama ----
function calcStats(arr) {
  let sum = 0, n = 0;
  for (const c of (arr || [])) {
    const r = Number(c?.rating);
    if (Number.isFinite(r) && r >= 1 && r <= 5) { sum += r; n++; }
  }
  return { avg: n ? (sum / n) : 0, total: n };
}
function starsFromAverage(avg) {
  const full = Math.floor(avg);
  const half = (avg % 1) >= 0.5 ? 1 : 0;
  return "★".repeat(full + half);
}
function getAvgFor(p) {
  return ratingMap[p.id]?.avg ?? 0;
}
function getTotalFor(p) {
  return ratingMap[p.id]?.total ?? 0;
}

// ---- Data fetch ----
async function fetchAllProducts() {
  try {
    const res = await fetch(`${BASE_URL}/products`);
    if (!res.ok) throw new Error(`API hata: ${res.status}`);
    allProducts = await res.json();
  } catch (err) {
    console.error("Ürünler çekilirken hata:", err);
    allProducts = [];
  }
}

// Tüm kategorilerin yorumlarını çekip ratingMap oluştur
async function buildRatingMap() {
  ratingMap = {};
  const cats = ["ayakkabi", "sapka", "sweat", "tshirt"];
  for (const cat of cats) {
    try {
      const res = await fetch(`${BASE_URL}/comments/${cat}`);
      if (!res.ok) continue;
      const byId = await res.json(); // { id: [ {user, rating, text?}, ... ] }
      for (const [pid, arr] of Object.entries(byId)) {
        ratingMap[pid] = calcStats(arr);
      }
    } catch (e) {
      console.warn("Yorumlar alınamadı:", cat, e);
    }
  }
}

// ---- Render ----
function applyFiltersAndSort() {
  const productList = document.getElementById("product-list");
  productList.innerHTML = "";

  // Kategori filtresi
  let filtered = allProducts.filter(p => currentCat === "all" ? true : p._cat === currentCat);

  // Fiyat aralığı
  const minPrice = parseFloat(document.getElementById("min-price")?.value) || 0;
  const maxPrice = parseFloat(document.getElementById("max-price")?.value) || Infinity;
  filtered = filtered.filter(p => p.price >= minPrice && p.price <= maxPrice);

  // Rating filtresi (GERÇEK ortalama ile)
  const ratingFilter = parseFloat(document.getElementById("rating-filter")?.value);
  if (ratingFilter) {
    filtered = filtered.filter(p => getAvgFor(p) >= ratingFilter);
  }

  // Sıralama
  const sortBy = document.getElementById("sort-select")?.value;
  if (sortBy === "price-asc") {
    filtered.sort((a, b) => a.price - b.price);
  } else if (sortBy === "price-desc") {
    filtered.sort((a, b) => b.price - a.price);
  } else if (sortBy === "rating-desc") {
    filtered.sort((a, b) => getAvgFor(b) - getAvgFor(a));
  }

  // Sonuçları göster
  if (filtered.length === 0) {
    productList.innerHTML = `
      <div class="no-results">
        <h3>Ürün bulunamadı</h3>
        <p>Arama kriterlerinizi değiştirerek tekrar deneyin.</p>
      </div>
    `;
    return;
  }

  // NeonGrid kart markup: .product-card içinde .product-img ve .product-card-info
  filtered.forEach(product => {
    const cacheBuster = Date.now();
    const imageUrl = product.images?.[0] || '';
    const imgUrl = imageUrl ? `${BASE_URL}/${imageUrl}?v=${cacheBuster}` : '';

    const avg = getAvgFor(product);
    const total = getTotalFor(product);
    const avgRounded = Math.round(avg * 10) / 10;

    const card = document.createElement("div");
    card.className = "product-card";
    card.innerHTML = `
      <a href="product.html?id=${encodeURIComponent(product.id)}&cat=${encodeURIComponent(product._cat)}" style="text-decoration:none; color:inherit;">
        <img src="${imgUrl}" alt="${product.name}" class="product-img" loading="lazy" />
        <div class="product-card-info">
          <h3>${product.name}</h3>
          <p class="price">${product.price} TL</p>
          <p class="rating">${starsFromAverage(avg)} ${avgRounded.toFixed(1)} ${total ? `(${total})` : ""}</p>
          <p class="category">${product.category}</p>
        </div>
      </a>
    `;
    productList.appendChild(card);
  });
}

async function renderProducts() {
  await Promise.all([fetchAllProducts(), buildRatingMap()]);
  applyFiltersAndSort();
}

// Button click ile kategori seçimi (event delegation)
const filterBar = document.getElementById("category-filter");
if (filterBar) {
  filterBar.addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-cat]");
    if (!btn) return;
    currentCat = btn.dataset.cat;

    // aktif buton görseli
    [...filterBar.querySelectorAll("button")].forEach(b => b.classList.remove("active"));
    btn.classList.add("active");

    applyFiltersAndSort();
  });
}

// Filtre değişikliklerini dinle
document.getElementById("sort-select")?.addEventListener("change", applyFiltersAndSort);
document.getElementById("rating-filter")?.addEventListener("change", applyFiltersAndSort);
document.getElementById("min-price")?.addEventListener("input", applyFiltersAndSort);
document.getElementById("max-price")?.addEventListener("input", applyFiltersAndSort);

window.addEventListener("DOMContentLoaded", renderProducts);

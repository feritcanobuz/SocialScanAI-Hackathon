// frontend/src/js/render.js (ecommerce2)
// NordWood teması: yatay kart + gerçek ortalama (backend rating-summary)

const BASE_URL = "http://127.0.0.1:8002";

let currentCat = "all";
let allProducts = [];
let ratingMap = {}; // { [productId]: { avg:number, total:number, counts?:{...} } }

// ---- Helpers ----
function starsFromAverage(avg) {
  // Yarım puanda bir yıldız daha gösteriyoruz (görsel amaçlı)
  const full = Math.floor(avg);
  const half = (avg % 1) >= 0.5 ? 1 : 0;
  return "⭐".repeat(full + half);
}
function getAvgFor(p)   { return typeof ratingMap[p.id]?.avg   === "number" ? ratingMap[p.id].avg   : 0; }
function getTotalFor(p) { return typeof ratingMap[p.id]?.total === "number" ? ratingMap[p.id].total : 0; }

// ---- Data fetch ----
async function fetchAllProducts() {
  const res = await fetch(`${BASE_URL}/products`);
  if (!res.ok) throw new Error(`API hata: ${res.status}`);
  allProducts = await res.json();
}

async function fetchRatingsFlat() {
  // Backend: {"ayk_01":{"avg":4.06,"total":29,"counts":{"1":0,"2":2,...}}, ...}
  const res = await fetch(`${BASE_URL}/rating-summary?flat=true`);
  ratingMap = res.ok ? await res.json() : {};
}

// ---- Render ----
function applyFiltersAndSort() {
  const productList = document.getElementById("product-list");
  productList.innerHTML = "";

  // Kategori filtresi
  let filtered = allProducts.filter(p => (currentCat === "all") ? true : p._cat === currentCat);

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

  if (filtered.length === 0) {
    productList.innerHTML = `
      <div class="no-results">
        <h3>Ürün bulunamadı</h3>
        <p>Arama kriterlerinizi değiştirerek tekrar deneyin.</p>
      </div>`;
    return;
  }

  // Kartlar: NordWood yatay kart yapısı (.product-card-h)
  filtered.forEach(product => {
    const cacheBuster = Date.now();
    const imageUrl = product.images?.[0] || "";
    const imgUrl = imageUrl ? `${BASE_URL}/${imageUrl}?v=${cacheBuster}` : "";
    const avg = getAvgFor(product);
    const total = getTotalFor(product);
    const avgText = avg ? avg.toFixed(1) : "0.0";

    const card = document.createElement("div");
    card.className = "product-card-h";
    card.innerHTML = `
      <a href="product.html?id=${encodeURIComponent(product.id)}&cat=${encodeURIComponent(product._cat)}">
        <div class="pc-h-img">
          <img src="${imgUrl}" alt="${product.name}">
        </div>
        <div class="pc-h-body">
          <h3 class="pc-h-title">${product.name}</h3>

          <div class="pc-h-meta">
            <span class="pc-badge">${product.category}</span>
            <span class="pc-stars">${starsFromAverage(avg)} ${avgText} ${total ? `(${total})` : ""}</span>
          </div>

          <p class="pc-desc">${product.description || ""}</p>

          <div class="pc-h-bottom">
            <span class="pc-price">${product.price} TL</span>
            <span class="pc-cta">Detaya Git →</span>
          </div>
        </div>
      </a>
    `;
    productList.appendChild(card);
  });
}

async function renderProducts() {
  try {
    await Promise.all([fetchAllProducts(), fetchRatingsFlat()]);
    applyFiltersAndSort();
  } catch (e) {
    console.error("Liste yüklenirken hata:", e);
    document.getElementById("product-list").innerHTML = `
      <div class="no-results">
        <h3>Bir sorun oluştu</h3>
        <p>Lütfen daha sonra tekrar deneyin.</p>
      </div>`;
  }
}

// Kategori butonları
const filterBar = document.getElementById("category-filter");
if (filterBar) {
  filterBar.addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-cat]");
    if (!btn) return;
    currentCat = btn.dataset.cat;
    [...filterBar.querySelectorAll("button")].forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    applyFiltersAndSort();
  });
}

// Filtreler
document.getElementById("sort-select")?.addEventListener("change", applyFiltersAndSort);
document.getElementById("rating-filter")?.addEventListener("change", applyFiltersAndSort);
document.getElementById("min-price")?.addEventListener("input", applyFiltersAndSort);
document.getElementById("max-price")?.addEventListener("input", applyFiltersAndSort);

window.addEventListener("DOMContentLoaded", renderProducts);

// frontend/src/js/render.js
const BASE_URL = "http://127.0.0.1:8001";

let currentCat = "all";
let allProducts = [];   // /products sonucunu tutar
let ratingMap = {};     // { "<productId>": { avg, total, counts } }

// Ürünleri çek
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

// Rating özetini çek (/rating-summary?flat=true -> flat map)
async function fetchRatingMap() {
  try {
    const res = await fetch(`${BASE_URL}/rating-summary?flat=true`);
    if (!res.ok) throw new Error(`Rating API hata: ${res.status}`);
    ratingMap = await res.json(); // { "ayk_01": {avg,total,counts}, ... }
  } catch (err) {
    console.error("Rating özeti çekilirken hata:", err);
    ratingMap = {};
  }
}

// Bir ürün için gösterilecek/filtrelenecek ortalama
function getAvg(product) {
  const r = ratingMap[product.id];
  if (r && typeof r.avg === "number") return r.avg;
  // fallback: product.json içindeki rating (geçici)
  return typeof product.rating === "number" ? product.rating : 0;
}

function applyFiltersAndSort() {
  const productList = document.getElementById("product-list");
  productList.innerHTML = "";

  // Kategori filtresi
  let filtered = allProducts.filter(p => currentCat === "all" ? true : p._cat === currentCat);

  // Fiyat aralığı filtresi
  const minPrice = parseFloat(document.getElementById("min-price").value) || 0;
  const maxPrice = parseFloat(document.getElementById("max-price").value) || Infinity;
  filtered = filtered.filter(p => p.price >= minPrice && p.price <= maxPrice);

  // Rating filtresi (gerçek ortalamaya göre)
  const ratingFilter = parseFloat(document.getElementById("rating-filter").value);
  if (ratingFilter) {
    filtered = filtered.filter(p => getAvg(p) >= ratingFilter);
  }

  // Sıralama
  const sortBy = document.getElementById("sort-select").value;
  if (sortBy === "price-asc") {
    filtered.sort((a, b) => a.price - b.price);
  } else if (sortBy === "price-desc") {
    filtered.sort((a, b) => b.price - a.price);
  } else if (sortBy === "rating-desc") {
    filtered.sort((a, b) => getAvg(b) - getAvg(a));
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

  filtered.forEach(product => {
    const cacheBuster = Date.now();
    const imageUrl = product.images?.[0] || "";
    const imgUrl = `${BASE_URL}/${imageUrl}?v=${cacheBuster}`;

    const avg = getAvg(product);
    const avgRounded = Math.round(avg * 10) / 10;

    const card = document.createElement("div");
    card.className = "product-card";
    card.innerHTML = `
      <a href="product.html?id=${encodeURIComponent(product.id)}&cat=${encodeURIComponent(product._cat)}" style="text-decoration:none; color:inherit;">
        <img src="${imgUrl}" alt="${product.name}" class="product-img" loading="lazy" />
        <div class="product-card-info">
          <h3>${product.name}</h3>
          <p class="price">${product.price} TL</p>
          <p class="rating">⭐ ${avgRounded.toFixed(1)}</p>
          <p class="category">${product.category}</p>
        </div>
      </a>
    `;
    productList.appendChild(card);
  });
}

async function renderProducts() {
  // Ürünler ve rating özetini paralel çek
  await Promise.all([fetchAllProducts(), fetchRatingMap()]);
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
document.getElementById("sort-select").addEventListener("change", applyFiltersAndSort);
document.getElementById("rating-filter").addEventListener("change", applyFiltersAndSort);
document.getElementById("min-price").addEventListener("input", applyFiltersAndSort);
document.getElementById("max-price").addEventListener("input", applyFiltersAndSort);

window.addEventListener("DOMContentLoaded", renderProducts);

// script.js - placed at static/css/js/script.js

document.addEventListener("DOMContentLoaded", () => {
  loadAds();
});

function showSpinner(show){
  const s = document.getElementById('spinner');
  if(!s) return;
  s.style.display = show ? 'block' : 'none';
}

async function loadAds(){
  showSpinner(true);
  try {
    const res = await fetch('/get_ads');
    const data = await res.json();
    renderAds(data);
  } catch(err){
    console.error("Failed to load ads", err);
  }
  showSpinner(false);
}

function renderAds(ads){
  const container = document.getElementById('ads-container');
  container.innerHTML = '';
  const top5 = ads.slice(0,5);
  top5.forEach(ad => {
    const col = document.createElement('div');
    col.className = 'col-md-4';
    col.innerHTML = `
      <div class="card ad-card" id="ad-card-${ad.id}">
        <img src="/static/images/${ad.image_url}" alt="${escapeHtml(ad.title)}">
        <div class="card-body">
          <h5 class="card-title">${escapeHtml(ad.title)}</h5>
          <p class="card-text text-muted">${escapeHtml(ad.category)} • CTR: ${Number(ad.ctr).toFixed(2)}%</p>
          <div>
            <a href="${ad.target_page}" class="btn btn-primary btn-sm" target="_blank">Visit</a>
            <button class="btn btn-outline-danger btn-sm ms-2" onclick="dislikeAd(${ad.id})">👎 Dislike</button>
          </div>
        </div>
      </div>
    `;
    container.appendChild(col);
  });
}

function escapeHtml(s){
  if(!s) return '';
  return String(s).replace(/[&<>"'`=\/]/g, function (c) {
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;','/':'&#x2F;','`':'&#x60;','=':'&#x3D;'}[c];
  });
}

async function dislikeAd(adId){
  // animate fade out of the card before refreshing
  const card = document.getElementById(`ad-card-${adId}`);
  if(card){
    card.classList.add('fade-out');
  }
  // wait for animation
  await new Promise(r => setTimeout(r, 450));
  try {
    await fetch(`/dislike/${adId}`, { method: 'POST' });
  } catch(err) {
    console.error('dislike error', err);
  }
  // reload ads without page refresh
  await loadAds();
}

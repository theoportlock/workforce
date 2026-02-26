(() => {
  const root = document.getElementById("app");
  if (!root) {
    return;
  }

  root.innerHTML = "";
  const fallback = document.createElement("div");
  fallback.className = "workforce-app-fallback";
  fallback.textContent = "Workforce frontend assets loaded.";
  root.appendChild(fallback);
})();

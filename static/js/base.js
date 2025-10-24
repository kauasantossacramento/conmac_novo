document.addEventListener("change", (e)=>{
  if (e.target.matches(".checklist input[type=checkbox]")) {
    const span = e.target.closest("form").querySelector(".texto");
    if (span) span.style.textDecoration = "underline";
  }
});


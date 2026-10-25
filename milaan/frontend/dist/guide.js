// A plain, accessible language switch for the existing native guide dialog.
const dialog=document.getElementById('help-dialog');
if(dialog){
  const choices=[...dialog.querySelectorAll('[data-guide-language]')];
  const selectLanguage=(lang)=>{
    if(!['en','ur'].includes(lang))return;
    for(const button of choices){
      button.setAttribute('aria-pressed',String(button.dataset.guideLanguage===lang));
    }
    for(const item of dialog.querySelectorAll('.guide-panel')){
      item.hidden=item.id!=='guide-'+lang;
    }
  };
  for(const button of choices){
    button.addEventListener('click',()=>selectLanguage(button.dataset.guideLanguage));
  }
  selectLanguage('en');
}

// Keep the keyboard inside whichever native modal is currently active.
document.addEventListener('keydown', event => {
  if (event.key !== 'Tab') return;
  const modal = [...document.querySelectorAll('dialog[open]')].at(-1);
  if (!modal || !modal.matches(':modal')) return;
  const focusable = [...modal.querySelectorAll('a[href],button,input,select,textarea,[tabindex]')]
    .filter(node => node.tabIndex >= 0 && !node.closest('[hidden]')
      && node.getClientRects().length > 0 && getComputedStyle(node).visibility !== 'hidden');
  if (!focusable.length) {
    event.preventDefault();
    modal.focus();
    return;
  }
  const first = focusable[0], last = focusable.at(-1), active = document.activeElement;
  if (event.shiftKey && (active === first || !modal.contains(active))) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && (active === last || !modal.contains(active))) {
    event.preventDefault();
    first.focus();
  }
}, true);

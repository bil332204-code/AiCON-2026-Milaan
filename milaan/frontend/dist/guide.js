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

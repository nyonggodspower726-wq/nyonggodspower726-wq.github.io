"use strict";
document.addEventListener("DOMContentLoaded",function(){
const $=s=>document.querySelector(s);
const $$=s=>document.querySelectorAll(s);
const body=document.body;
const currentPage=location.pathname.split("/").pop()||"index.html";
const dateText=new Date().toLocaleDateString("en-US",{weekday:"long",year:"numeric",month:"long",day:"numeric"});
$$("[data-current-date],#headerDate").forEach(e=>e.textContent=dateText);
$$("[data-current-year]").forEach(e=>e.textContent=new Date().getFullYear());
const themeButton=$("#themeButton")||$("[data-theme-toggle]")||$("#themeToggle")||$(".theme-toggle");
const savedTheme=localStorage.getItem("anf-theme")||localStorage.getItem("ai-news-theme");
if(savedTheme==="light")body.classList.add("light-mode");
if(themeButton)themeButton.addEventListener("click",function(){
body.classList.toggle("light-mode");
localStorage.setItem("anf-theme",body.classList.contains("light-mode")?"light":"dark");
});
const menuButton=$("#menuToggle")||$("[data-menu-toggle]")||$(".menu-toggle");
const navigation=$(".main-nav")||$("nav");
if(menuButton&&navigation){
menuButton.setAttribute("aria-expanded","false");
menuButton.addEventListener("click",function(){
const open=navigation.classList.toggle("is-open");
menuButton.classList.toggle("is-active",open);
menuButton.setAttribute("aria-expanded",String(open));
});
}
const searchButton=$("#searchButton")||$("#searchToggle")||$("[data-search-toggle]")||$(".search-toggle");
const searchPanel=$("#searchPanel")||$("[data-search-panel]")||$(".search-panel");
const searchInput=$("#searchInput")||$("[data-search-input]")||$(".search-input");
if(searchButton)searchButton.addEventListener("click",function(){
if(searchPanel){
const open=searchPanel.classList.toggle("is-open");
if(open&&searchInput)setTimeout(()=>searchInput.focus(),100);
}else location.href="search.html";
});
if(searchInput)searchInput.addEventListener("keydown",function(e){
if(e.key==="Enter"){
const q=this.value.trim();
if(q)location.href="search.html?q="+encodeURIComponent(q);
}
});
$$("a[data-category],.category-link").forEach(link=>{
link.addEventListener("click",function(e){
const category=this.dataset.category;
if(category){e.preventDefault();location.href="category.html?category="+encodeURIComponent(category);}
});
});
$$("[data-story],.story-link").forEach(link=>{
link.addEventListener("click",function(e){
const slug=this.dataset.story||this.dataset.slug;
if(slug){e.preventDefault();location.href="article.html?slug="+encodeURIComponent(slug);}
});
});
$$("nav a").forEach(link=>{
const href=link.getAttribute("href");
if(!href)return;
const page=href.split("?")[0].split("#")[0];
if(page===currentPage||(currentPage==="index.html"&&page===""))link.classList.add("active");
});
$$("[data-back-to-top],#backToTop,.back-to-top").forEach(button=>{
const update=()=>button.classList.toggle("is-visible",scrollY>500);
window.addEventListener("scroll",update,{passive:true});
button.addEventListener("click",()=>scrollTo({top:0,behavior:"smooth"}));
update();
});
$$('a[href^="#"]').forEach(link=>{
link.addEventListener("click",function(e){
const id=this.getAttribute("href");
if(!id||id==="#")return;
const target=$(id);
if(target){e.preventDefault();target.scrollIntoView({behavior:"smooth",block:"start"});}
});
});
document.addEventListener("keydown",function(e){
if(e.key!=="Escape")return;
if(searchPanel)searchPanel.classList.remove("is-open");
if(navigation)navigation.classList.remove("is-open");
if(menuButton)menuButton.setAttribute("aria-expanded","false");
});
$$("[data-live-indicator],.live-indicator").forEach(e=>e.setAttribute("aria-label","Newsroom live"));
$$("[data-factory-status]").forEach(e=>{e.textContent="NEWSROOM ONLINE";e.classList.add("online");});
$$("[data-newsletter-form],.newsletter-form").forEach(form=>{
form.addEventListener("submit",function(e){
e.preventDefault();
const input=this.querySelector('input[type="email"]');
if(!input)return;
if(!input.value.trim()){alert("Please enter your email address.");input.focus();return;}
if(!input.checkValidity()){alert("Please enter a valid email address.");input.focus();return;}
alert("You're on the list. AI News Factory will keep you updated.");
input.value="";
});
});
console.log("%cAI NEWS FACTORY","font-size:18px;font-weight:bold;");
console.log("Newsroom interface initialized successfully.");
});

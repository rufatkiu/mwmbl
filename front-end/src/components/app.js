import define from '../utils/define.js';

const template = () => /*html*/`
  <header class="search-menu">
    <div class="branding">
      <img class="brand-icon" src="/static/images/logo.svg" width="40" height="40" alt="mwmbl logo">
      <span class="brand-title">MWMBL</span>
    </div>
    <mwmbl-search-bar></mwmbl-search-bar>
  </header>
    <main>
      <mwmbl-results></mwmbl-results>
    </main>
  <footer is="mwmbl-footer"></footer>
`;

export default define('app', class extends HTMLElement {
  constructor() {
    super();
    this.__setup();
  }

  __setup() {
    this.innerHTML = template();
  }
});
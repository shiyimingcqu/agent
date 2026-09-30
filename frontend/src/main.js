// ============================================================
// main.js —— 整个前端应用的“入口文件”
// ============================================================
//
// 浏览器加载页面后，第一个执行的 JS 就是这个文件（由 index.html 引入）。
// 它只做一件事：创建 Vue 应用，并把它挂到页面上。

// createApp 是 Vue 提供的函数，用来“造”一个应用实例。
import { createApp } from "vue";

// 导入根组件 App.vue。
// 后面所有界面（包括聊天框）都从它开始一层层展开，所以它叫“根组件”。
// 结构像一棵组件树：App（根） -> ChatBox（子）。
import App from "./App.vue";

// createApp(App)：用根组件创建一个 Vue 应用。
// .mount("#app")：把它挂载到 index.html 里 id="app" 的那个 div 上。
// 挂载之后，这个 div 就交给 Vue 接管，界面由 Vue 负责渲染。
// 注意 "#app" 是 CSS 选择器写法，对应 <div id="app"></div>。
createApp(App).mount("#app");
<!--
  App.vue 是“根组件”，负责整体布局；
  真正的聊天功能拆到了子组件 ChatBox.vue 里，这叫“组件化”：
  每个组件只管一件事，拼起来就是完整页面。
-->

<script setup>
// <script setup> 是 Vue 3 的语法糖（单文件组件专用）。
// 在这个标签里 import 的组件、定义的变量和函数，
// 都能直接在下面的 <template> 里使用，不需要再手动 export / return。

// 导入子组件 ChatBox。
// 导入后，模板里就能像写 HTML 标签一样用它，写法是 <ChatBox />。
import ChatBox from "./components/ChatBox.vue";
</script>

<template>
  <!-- template 决定这个组件“长什么样”。
       一个 .vue 文件 = script(逻辑) + template(结构) + style(样式) 三部分。 -->
  <main class="app">
    <h1>Agent</h1>

    <!-- 使用子组件：它会把自己界面渲染到这个位置 -->
    <ChatBox />
  </main>
</template>

<style>
/* 这个 style 没加 scoped，属于“全局样式”，会影响整个应用。
   一般只在设置 body 这类全局规则时才这么写。 */
body {
  font-family: system-ui, "Microsoft YaHei", sans-serif;
  margin: 0;
}
.app {
  max-width: 640px;   /* 内容最宽 640px，避免在宽屏上拉得太长 */
  margin: 60px auto;  /* 上下留白 60px；左右 auto 表示水平居中 */
  padding: 0 16px;    /* 左右各留 16px 内边距，防止贴边 */
}
</style>
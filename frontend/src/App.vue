<script setup>
// ============================================================
// App.vue —— 根组件：负责“登录页 / 聊天页”的切换
// ============================================================
//
// 页面一打开，它会去问后端“我现在是谁”：
//   已登录 -> 显示聊天页 ChatBox
//   未登录 -> 显示登录页 Login
// 这个判断通过 /auth/me 接口完成（后端会读取浏览器 Cookie 里的登录凭证）。

import { ref, onMounted } from "vue";

// 导入两个子组件：登录组件、聊天组件
import Login from "./components/Login.vue";
import ChatBox from "./components/ChatBox.vue";

// ---------- 两个状态 ----------

// 当前登录的用户信息；null 表示“还没登录”
const user = ref(null);

// 是否还在检查登录状态。
// 作用：避免页面刚打开时先闪一下登录页、再跳成聊天页的尴尬。
const checking = ref(true);

// onMounted：组件挂载到页面后自动执行一次。
// 时机正好是“页面刚打开”，适合用来检查登录状态。
onMounted(async () => {
  try {
    const resp = await fetch("/auth/me");

    if (resp.ok) {
      // 200：说明带着有效 Cookie，已登录，把用户信息存下来
      user.value = await resp.json();
    }
    // 非 200（比如 401）：保持 user 为 null，即当成未登录
  } catch (e) {
    // 后端没启动等异常，不阻断页面，只打印错误
    console.error("检查登录状态失败：", e);
  } finally {
    // 无论成功还是失败，都要结束“检查中”状态，好让页面继续渲染
    checking.value = false;
  }
});

// 登录页登录成功后，会发出 logged-in 事件把用户信息传进来
function onLoggedIn(u) {
  user.value = u;  // 一旦有用户，界面就会自动切换到聊天页
}

// 退出登录：通知后端删除会话，然后把本地状态清空回到登录页
async function logout() {
  await fetch("/auth/logout", { method: "POST" });
  user.value = null;
}
</script>

<template>
  <main class="app">
    <h1>Agent</h1>

    <!-- 第一步：还在检查登录状态时，先显示“加载中…” -->
    <p v-if="checking">加载中…</p>

    <!-- 第二步：检查完成后，根据 user 是否存在来决定显示哪一页 -->
    <template v-else>
      <!-- 已登录：顶部显示用户名和登出按钮 -->
      <div v-if="user" class="userbar">
        <span>当前用户：{{ user.username }}</span>
        <button @click="logout">登出</button>
      </div>

      <!-- 已登录：显示聊天组件。
           @unauthorized：聊天组件发现登录过期时会通知这里，我们就执行 logout -->
      <ChatBox v-if="user" @unauthorized="logout" />

      <!-- 未登录：显示登录组件。
           @logged-in="onLoggedIn"：监听子组件发出的 logged-in 事件 -->
      <Login v-else @logged-in="onLoggedIn" />
    </template>
  </main>
</template>

<style>
/* 这个 style 没有 scoped，属于“全局样式”，会影响整个应用。
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

/* 顶部“当前用户 / 登出”那一行 */
.userbar {
  display: flex;
  justify-content: space-between;  /* 文字靠左、按钮靠右 */
  align-items: center;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #eee;
  color: #555;
  font-size: 14px;
}
.userbar button {
  padding: 6px 12px;
  cursor: pointer;
}
</style>
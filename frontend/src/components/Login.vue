<script setup>
// ============================================================
// Login.vue —— 登录 / 注册 组件
// ============================================================
//
// 这个组件同时负责“登录”和“注册”，用一个开关 isRegister 切换。
// 为什么放一起？因为两者界面几乎一样（都是用户名 + 密码），
// 合起来能少写一份重复的代码。

import { ref } from "vue";

// defineEmits：声明这个组件会向“父组件”发出哪些事件。
// 登录成功后，它发一个 "logged-in" 事件，把用户信息交给父组件 App。
// 父组件收到后，就会把界面从“登录页”换成“聊天页”。
const emit = defineEmits(["logged-in"]);

// ---------- 页面用到的状态 ----------
// 带 ref 的变量叫“响应式变量”：值一变，界面自动更新。
const username = ref("");       // 用户名输入框里的内容
const password = ref("");       // 密码输入框里的内容
const error = ref("");          // 红色错误提示文字
const message = ref("");        // 绿色成功提示文字
const loading = ref(false);     // 是否正在请求（请求期间禁用按钮）
const isRegister = ref(false);  // false=登录模式，true=注册模式

// 在“登录 / 注册”两个模式之间来回切换
function toggle() {
  isRegister.value = !isRegister.value;
  error.value = "";
  message.value = "";
}

// 点击“登录”或“注册”按钮时执行
async function submit() {
  // 每次提交前，先把旧的提示清掉
  error.value = "";
  message.value = "";

  // 简单校验：两个框都不能为空
  if (!username.value || !password.value) {
    error.value = "请输入用户名和密码";
    return;
  }

  loading.value = true;
  try {
    // 根据当前模式，决定请求哪个后端接口
    // 注册 -> /auth/register ；登录 -> /auth/login
    const url = isRegister.value ? "/auth/register" : "/auth/login";

    const resp = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: username.value,
        password: password.value,
      }),
    });

    // 后端出错时返回的内容形如 {"detail": "错误原因"}。
    // .catch(() => ({})) 是容错：万一响应体为空（比如请求没转发到后端），
    // 也不会抛出 "Unexpected end of JSON input" 这种难懂的报错。
    const data = await resp.json().catch(() => ({}));

    if (!resp.ok) {
      // resp.ok 为 false 表示状态码不是 2xx（如 400、401、409）
      error.value = data.detail || `请求失败（状态码 ${resp.status}）`;
      return;
    }

    if (isRegister.value) {
      // 注册成功：切回登录模式，并提示用户去登录
      isRegister.value = false;
      password.value = "";
      message.value = "注册成功，请登录";
    } else {
      // 登录成功：把用户信息发给父组件 App
      emit("logged-in", data);
    }
  } catch (e) {
    // 网络断了、后端没启动等情况会走到这里
    error.value = "网络错误：" + e.message;
  } finally {
    // 不管成功还是失败，最后都要取消“请求中”状态
    loading.value = false;
  }
}
</script>

<template>
  <div class="login">
    <!-- 标题随模式变化：登录模式显示“登录”，注册模式显示“注册” -->
    <h2>{{ isRegister ? "注册" : "登录" }}</h2>

    <!-- v-model：把输入框和上面定义的变量双向绑定。
         输入框内容变 -> username 自动更新；代码改 username -> 输入框自动更新。 -->
    <input v-model="username" placeholder="用户名" />

    <!-- type="password"：输入的内容显示成圆点，防止被别人看到 -->
    <!-- @keydown.enter：在密码框里按回车也能直接提交 -->
    <input
      v-model="password"
      type="password"
      placeholder="密码"
      @keydown.enter="submit"
    />

    <!-- v-if：只有变量有内容时才渲染这一行 -->
    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="message" class="success">{{ message }}</p>

    <!-- 按钮：请求中禁用，文案变成“处理中…” -->
    <button @click="submit" :disabled="loading">
      {{ loading ? "处理中…" : isRegister ? "注册" : "登录" }}
    </button>

    <!-- 一键切换登录 / 注册 -->
    <p class="switch">
      <span v-if="isRegister">已有账号？<a @click="toggle">去登录</a></span>
      <span v-else>没有账号？<a @click="toggle">去注册</a></span>
    </p>
  </div>
</template>

<style scoped>
/* scoped：样式只作用于当前组件，不会影响别的组件 */
.login {
  display: flex;
  flex-direction: column;  /* 内容从上到下竖着排 */
  gap: 10px;               /* 每行之间留 10px 间距 */
  max-width: 320px;        /* 登录框最宽 320px */
  margin: 0 auto;          /* 水平居中 */
}
.login h2 {
  margin: 0 0 4px;
}
.login input {
  padding: 10px;
  font-size: 14px;
}
.login button {
  padding: 10px;
  font-size: 15px;
  cursor: pointer;
}
.error {
  color: #d1242f;  /* 红色：错误提示 */
  margin: 0;
  font-size: 14px;
}
.success {
  color: #1a7f37;  /* 绿色：成功提示 */
  margin: 0;
  font-size: 14px;
}
.switch {
  margin: 0;
  font-size: 14px;
  color: #555;
}
.switch a {
  color: #0969da;  /* 蓝色：像链接一样可点 */
  cursor: pointer;
}
</style>
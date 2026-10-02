<script setup>
// ============================================================
// ChatBox.vue —— 聊天框组件：加载历史 + 输入问题 + 显示对话 + 请求后端
// ============================================================
//
// <script setup> 是 Vue 3 的语法糖：
// 这里定义的变量和函数可以直接在下面的 <template> 里使用。

// ref：创建响应式变量；onMounted：组件挂载完成后执行一次的“生命周期钩子”。
import { ref, onMounted } from "vue";

// defineEmits：声明本组件会对“父组件”发出 "unauthorized" 事件。
// 当后端返回 401（登录已过期）时，我们就发这个事件，
// 让父组件 App 收到后把我们切回登录页。
const emit = defineEmits(["unauthorized"]);

// ---------- 三个响应式状态 ----------
// 小提醒：在 <script> 里读写要用 .value；在 <template> 里 Vue 会自动帮你取值。

const question = ref("");   // 输入框里的文字
const logs = ref([]);       // 对话记录数组，每项形如 { role: "user"/"agent", text: "..." }
const loading = ref(false); // 是否正在等后端返回（用来禁用按钮、显示“思考中”）
const uploading = ref(false); // 是否正在上传文件（按钮会显示“上传中…”）

// ---------- 页面加载时：拉取历史对话 ----------
// onMounted 里的代码会在组件“挂载到页面后”自动执行一次。
// 这正是我们想要的时机：页面一打开，就把数据库里的历史记录显示出来。
onMounted(async () => {
  try {
    // 请求后端的 /history 接口（同样由 vite.config.js 的 proxy 转发）
    const resp = await fetch("/history");

    // 401 = 没登录或登录已过期，通知父组件切回登录页
    if (resp.status === 401) {
      emit("unauthorized");
      return;
    }

    const data = await resp.json();  // 形如 {"messages": [{role, text, created_at}, ...]}

    // 数据库字段是 content，界面用的是 text，这里做一次转换
    logs.value = data.messages.map((m) => ({ role: m.role, text: m.text }));
  } catch (e) {
    // 加载历史失败不影响发消息，这里只打印错误，不打断界面
    console.error("加载历史失败：", e);
  }
});

// ---------- 上传文件到 RAG 知识库 ----------
// 前端不需要解析文件内容，只负责把文件交给后端 /documents/upload，
// 由后端 rag.add_document 完成切块、转向量、入库。

// 隐藏的 <input type="file"> 由上传按钮触发点击，
// 好处是样式完全可控，不用依赖浏览器默认的文件选择框外观。
const fileInput = ref(null);

// 用户点“上传”按钮：模拟点击隐藏的文件选择框
function pickFile() {
  fileInput.value.click();
}

// 用户选中文件后触发：表单自动带上文件并 POST 给后端
async function onFileSelected(e) {
  // e.target.files 是选中的文件列表，[0] 取第一个
  const file = e.target.files[0];
  if (!file || uploading.value) return;

  // 上传中禁止重复选择（同时清空选择框，允许再次选同一个文件）
  uploading.value = true;
  e.target.value = "";

  try {
    // FormData：专用于“文件 + 表单字段”的数据格式，会自动加 multipart 头
    const form = new FormData();
    form.append("file", file);

    const resp = await fetch("/documents/upload", {
      method: "POST",
      body: form, // 注意：文件上传不能手动设 Content-Type，浏览器会自动带 boundary
    });

    if (!resp.ok) {
      // /documents/upload 里 HTTPException 是 4xx/5xx，resp.ok 为 false 时读取错误信息
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || "上传失败，状态码 " + resp.status);
    }

    const data = await resp.json();
    logs.value.push({
      role: "agent",
      text: `【已入库】${data.filename}：${data.characters} 字，切分后已可检索。`,
    });
  } catch (e) {
    logs.value.push({ role: "agent", text: "上传失败：" + e.message });
  } finally {
    uploading.value = false;
  }
}

// ---------- 发送问题的函数 ----------
async function ask() {
  // .trim() 去掉首尾空格；question.value 取出 ref 当前的值
  const message = question.value.trim();

  // 内容为空，或正在请求中，就直接返回，避免重复发送
  if (!message || loading.value) return;

  // 1) 先把用户这句话加进对话记录（界面会自动多出一行）
  logs.value.push({ role: "user", text: message });

  // 2) 清空输入框（因为 v-model，界面上的输入框也会一起变空）
  question.value = "";

  // 3) 标记“正在请求”：按钮会被禁用，并显示“思考中…”
  loading.value = true;

  try {
    // 4) 用 fetch 把问题发给后端。
    //    路径写 "/chat"：请求先发给 Vite(5173)，
    //    再由 vite.config.js 里的 proxy 转发给 FastAPI(8000)，从而避开跨域。
    const resp = await fetch("/chat", {
      method: "POST",                                  // 用 POST 提交数据
      headers: { "Content-Type": "application/json" }, // 声明请求体是 JSON
      body: JSON.stringify({ message }),               // 把对象转成 JSON 字符串发送
    });

    // 401 = 登录已过期，通知父组件切回登录页
    if (resp.status === 401) {
      emit("unauthorized");
      return;
    }

    // 5) 解析后端返回的 JSON，形如 {"answer": "..."}
    const data = await resp.json();

    // 6) 把 Agent 的回答也加进对话记录
    logs.value.push({ role: "agent", text: data.answer });
  } catch (e) {
    // 网络错误、后端没启动等异常会进到这里，把错误显示出来方便排查
    logs.value.push({ role: "agent", text: "请求失败：" + e.message });
  } finally {
    // 7) 不管成功还是失败，最后都要取消“正在请求”状态
    loading.value = false;
  }
}
</script>

<template>
  <section>
    <!-- ===== 对话记录区 ===== -->
    <div class="log">
      <!-- v-for：把 logs 里每一条渲染成一个 <p>。
           (m, i) 分别是“当前项”和“下标”；:key 给每项唯一标识，用下标即可。
           :class="m.role"：动态绑定 class，user 为绿色、agent 为深灰。 -->
      <p v-for="(m, i) in logs" :key="i" :class="m.role">
        <!-- {{ }} 是插值语法，会把变量值显示成文本。
             三元表达式决定前缀是“你：”还是“Agent：”。 -->
        {{ m.role === "user" ? "你：" : "Agent：" }}{{ m.text }}
      </p>

      <!-- v-if：条件为真才渲染这段，用来显示“思考中…”提示 -->
      <p class="agent" v-if="loading">Agent：思考中…</p>
    </div>

    <!-- ===== 输入区 ===== -->
    <div class="row">
      <!-- 隐藏的文件选择框：只支持 .txt（后端只解析 UTF-8 文本）。
           accept 是浏览器端的提示过滤，不是强制限制，后端还有二次校验。 -->
      <input
        ref="fileInput"
        type="file"
        accept=".txt"
        style="display: none"
        @change="onFileSelected"
      />

      <!-- 上传按钮：把文件交给 RAG 知识库，上传中禁用并改文案 -->
      <button @click="pickFile" :disabled="uploading">
        {{ uploading ? "上传中…" : "上传" }}
      </button>

      <!-- v-model：双向绑定。
             输入框内容变 -> question 自动更新；
             代码里改 question -> 输入框自动更新。
           @keydown.enter：在输入框按回车时调用 ask()。
           注意写的是 ask，不带括号：这是把函数“交给”事件，而不是立刻执行它。 -->
      <input v-model="question" @keydown.enter="ask" placeholder="问点什么，比如：现在几点？" />

      <!-- @click：点击时调用 ask()
           :disabled="loading"：请求进行中时禁用按钮，防止连点 -->
      <button @click="ask" :disabled="loading">发送</button>
    </div>
  </section>
</template>

<style scoped>
/* scoped：样式只作用于当前组件。
   Vue 会自动给这里的元素加上唯一属性，避免影响到别的组件。 */
.log {
  background: #f5f5f5;
  padding: 12px;
  border-radius: 8px;
  min-height: 80px;       /* 还没消息时也保持一定高度 */
}
.log p {
  margin: 4px 0;
  white-space: pre-wrap;  /* 保留换行和空格，长文本自动换行 */
}
.user { color: #1a7f37; }   /* 用户消息：绿色 */
.agent { color: #1f2937; }  /* Agent 消息：深灰 */
.row {
  display: flex;    /* 输入框和按钮横向排列 */
  gap: 8px;         /* 两者间距 8px */
  margin-top: 12px;
}
input {
  flex: 1;          /* 输入框占满剩余宽度 */
  padding: 8px;
}
button {
  padding: 8px 16px;
}
</style>
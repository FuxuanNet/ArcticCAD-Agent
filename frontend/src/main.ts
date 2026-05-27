import { createPinia } from "pinia"
import { createApp } from "vue"
import { install as VueMonacoEditorPlugin } from "@guolao/vue-monaco-editor"
import App from "./App.vue"
import router from "./router"
import "./styles/globals.css"

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(VueMonacoEditorPlugin, {
  paths: {
    vs: "https://cdn.jsdelivr.net/npm/monaco-editor@0.55.1/min/vs",
  },
})

app.mount("#app")

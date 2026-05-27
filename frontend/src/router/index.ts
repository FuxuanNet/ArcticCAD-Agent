import { createRouter, createWebHistory } from "vue-router"
import ProjectListView from "@/views/ProjectListView.vue"
import SettingsView from "@/views/SettingsView.vue"
import WorkbenchView from "@/views/WorkbenchView.vue"

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: "/",
      redirect: "/projects",
    },
    {
      path: "/projects",
      name: "projects",
      component: ProjectListView,
    },
    {
      path: "/projects/:projectId",
      name: "workbench",
      component: WorkbenchView,
    },
    {
      path: "/projects/:projectId/conversations/:conversationId",
      name: "conversation-workbench",
      component: WorkbenchView,
    },
    {
      path: "/settings",
      name: "settings",
      component: SettingsView,
    },
  ],
})

export default router

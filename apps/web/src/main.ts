import "element-plus/es/components/card/style/css";
import "element-plus/es/components/tag/style/css";
import "./styles.css";

import { ElCard, ElTag } from "element-plus";
import { createPinia } from "pinia";
import { createApp } from "vue";

import App from "./App.vue";
import { router } from "./router";

createApp(App)
  .component("ElCard", ElCard)
  .component("ElTag", ElTag)
  .use(createPinia())
  .use(router)
  .mount("#app");

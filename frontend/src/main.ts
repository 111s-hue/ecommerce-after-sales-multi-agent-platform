import { createApp } from 'vue'
import { ElAlert } from 'element-plus/es/components/alert/index'
import { ElButton } from 'element-plus/es/components/button/index'
import { ElDialog } from 'element-plus/es/components/dialog/index'
import { ElDrawer } from 'element-plus/es/components/drawer/index'
import { ElEmpty } from 'element-plus/es/components/empty/index'
import { ElIcon } from 'element-plus/es/components/icon/index'
import { ElInput } from 'element-plus/es/components/input/index'
import { ElLoading } from 'element-plus/es/components/loading/index'
import { ElTable, ElTableColumn } from 'element-plus/es/components/table/index'
import 'element-plus/dist/index.css'
import App from './App.vue'
import './style.css'
import './prototype-theme.css'

const app = createApp(App)
for (const component of [ElAlert, ElButton, ElDialog, ElDrawer, ElEmpty, ElIcon, ElInput, ElTable, ElTableColumn]) {
  app.use(component)
}
app.directive('loading', ElLoading.directive)
app.mount('#app')

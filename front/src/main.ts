import {
  ActionSheet,
  Button,
  Cell,
  CellGroup,
  Collapse,
  CollapseItem,
  ConfigProvider,
  Dialog,
  Empty,
  Field,
  Form,
  Grid,
  GridItem,
  Icon,
  Image,
  List,
  Loading,
  NavBar,
  Popup,
  Progress,
  PullRefresh,
  Radio,
  RadioGroup,
  Rate,
  Slider,
  Space,
  SwipeCell,
  Switch,
  Tab,
  Tabbar,
  TabbarItem,
  Tabs,
  Tag,
  Toast,
  Uploader,
} from 'vant';
import { createApp } from 'vue';
import App from './App.vue';
import router from './router';
import pinia from './store';
import 'vant/lib/index.css';
import './style.css';
import { setupI18n } from './i18n';

const app = createApp(App);
const i18n = setupI18n();
app.use(i18n);

app.use(Button);
app.use(NavBar);
app.use(Tabbar);
app.use(TabbarItem);
app.use(Tab);
app.use(Tabs);
app.use(List);
app.use(PullRefresh);
app.use(Cell);
app.use(CellGroup);
app.use(Grid);
app.use(GridItem);
app.use(Empty);
app.use(Form);
app.use(Field);
app.use(Image);
app.use(Toast);
app.use(Icon);
app.use(Popup);
app.use(Radio);
app.use(RadioGroup);
app.use(Collapse);
app.use(CollapseItem);
app.use(Rate);
app.use(Slider);
app.use(Tag);
app.use(Loading);
app.use(Dialog);
app.use(ConfigProvider);
app.use(Uploader);
app.use(Progress);
app.use(Switch);
app.use(ActionSheet);
app.use(SwipeCell);
app.use(Space);

app.use(router);
app.use(pinia);
app.mount('#app');

import { useThemeStore } from './store/theme';

const themeStore = useThemeStore();
themeStore.initTheme();

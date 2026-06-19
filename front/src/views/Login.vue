<template>
  <van-nav-bar
    title="用户登录"
    left-arrow
    @click-left="onClickLeft"
    fixed
    placeholder
  />

  <div>
    <van-icon name="service-o" size="40" />
    <h2>RAG 智能问答</h2>
  </div>

  <van-form @submit="onSubmit">
    <van-cell-group inset>
      <van-field
        v-model="username"
        name="username"
        label="用户名"
        placeholder="请输入用户名"
        :rules="[{ required: true, message: '请填写用户名' }]"
      />
      <van-field
        v-model="password"
        type="password"
        name="password"
        label="密码"
        placeholder="请输入密码"
        :rules="[{ required: true, message: '请填写密码' }]"
      />
    </van-cell-group>

    <van-space direction="vertical" :size="16" fill>
      <van-button round block type="primary" native-type="submit" size="large">
        登录
      </van-button>
      <van-button round block type="default" size="large" @click="loginTestUser">
        测试用户登录
      </van-button>
    </van-space>

    <div>
      还没有账号？<span @click="goToRegister">去注册</span>
    </div>
  </van-form>
</template>

<script setup>
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { showToast } from 'vant';
import { useUserStore } from '../store/user';

const router = useRouter();
const userStore = useUserStore();

const username = ref('');
const password = ref('');

const onSubmit = async (values) => {
  showToast({
    type: 'loading',
    message: '登录中...',
    forbidClick: true,
    duration: 0
  });

  try {
    const result = await userStore.login({
      username: username.value,
      password: password.value
    });

    if (result.success) {
      showToast({
        type: 'success',
        message: result.message
      });
      router.push('/');
    } else {
      showToast({
        type: 'fail',
        message: result.message
      });
    }
  } catch (error) {
    showToast({
      type: 'fail',
      message: '登录失败，请稍后再试'
    });
  }
};

const onClickLeft = () => {
  router.back();
};

const goToRegister = () => {
  router.push('/register');
};

const loginTestUser = () => {
  username.value = 'test';
  password.value = '666666';
};
</script>

<template>
  <van-nav-bar
    title="用户注册"
    left-arrow
    @click-left="onClickLeft"
    fixed
    placeholder
  />

  <div class="flex flex-col items-center gap-8 px-4 mt-8">
    <div class="flex flex-col items-center gap-3">
      <Bot :size="48" color="var(--van-primary-color)" />
      <h2 class="text-xl font-semibold m-0">用户注册</h2>
    </div>

    <div class="w-full flex flex-col gap-6">
      <van-cell-group inset>
        <van-field
          v-model="form.username"
          label="用户名"
          placeholder="请输入用户名"
          :rules="usernameRules"
          required
          @blur="validateUsername"
        />
        <van-field
          v-model="form.email"
          label="邮箱"
          placeholder="请输入邮箱地址"
          :rules="emailRules"
          required
          type="email"
          @blur="validateEmail"
        />
        <van-field
          v-model="form.telephone"
          label="手机号"
          placeholder="请输入手机号码"
          type="tel"
          maxlength="11"
        />
        <van-field
          v-model="form.password"
          label="密码"
          placeholder="请输入密码（6-20位）"
          :rules="passwordRules"
          required
          type="password"
          @blur="validatePassword"
        />
        <van-field
          v-model="form.confirm_password"
          label="确认密码"
          placeholder="请确认密码"
          :rules="confirmPasswordRules"
          required
          type="password"
          @blur="validateConfirmPassword"
        />
      </van-cell-group>

      <div class="flex flex-col gap-3 px-4">
        <van-button
          type="primary"
          block
          size="large"
          :loading="loading"
          @click="handleRegister"
        >
          {{ loading ? '注册中...' : '注册' }}
        </van-button>
      </div>

      <div class="text-center text-sm text-gray-500">
        已有账号？<span class="text-blue-500" @click="goToLogin">去登录</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Bot } from '@lucide/vue';
import { showToast } from 'vant';
import { reactive, ref } from 'vue';
import { useRouter } from 'vue-router';
import { useUserStore } from '../store/user';

const router = useRouter();
const userStore = useUserStore();

const loading = ref(false);

const form = reactive({
  username: '',
  email: '',
  telephone: '',
  password: '',
  confirm_password: ''
});

const usernameRules = [
  { required: true, message: '请输入用户名' }
];

const emailRules = [
  { required: true, message: '请输入邮箱地址' },
  { pattern: /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/, message: '请输入正确的邮箱地址' }
];

const passwordRules = [
  { required: true, message: '请输入密码' },
  { pattern: /^.{6,20}$/, message: '密码长度应为6-20位' }
];

const confirmPasswordRules = [
  { required: true, message: '请确认密码' }
];

const validateUsername = () => {
  if (!form.username) {
    showToast('请输入用户名');
    return false;
  }
  return true;
};

const validateEmail = () => {
  if (!form.email) {
    showToast('请输入邮箱地址');
    return false;
  }
  const emailRegex = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
  if (!emailRegex.test(form.email)) {
    showToast('请输入正确的邮箱地址');
    return false;
  }
  return true;
};

const validatePassword = () => {
  if (!form.password) {
    showToast('请输入密码');
    return false;
  }
  if (form.password.length < 6 || form.password.length > 20) {
    showToast('密码长度应为6-20位');
    return false;
  }
  return true;
};

const validateConfirmPassword = () => {
  if (!form.confirm_password) {
    showToast('请确认密码');
    return false;
  }
  if (form.password !== form.confirm_password) {
    showToast('两次输入的密码不一致');
    return false;
  }
  return true;
};

const validateForm = () => {
  return validateUsername() && validateEmail() && validatePassword() && validateConfirmPassword();
};

const handleRegister = async () => {

  if (!validateForm()) {
    return;
  }
  loading.value = true;

  try {
    const result = await userStore.register(form);

    if (result.success) {
      showToast({
        message: result.message,
        position: 'top'
      });

      setTimeout(() => {
        router.push('/aichat');
      }, 1500);
    } else {
      showToast({
        message: result.message,
        position: 'top',
        type: 'fail'
      });
    }
  } catch (error) {
    showToast({
      message: '注册失败，请稍后重试',
      position: 'top',
      type: 'fail'
    });
  } finally {
    loading.value = false;
  }
};

const onClickLeft = () => {
  router.back();
};

const goToLogin = () => {
  router.push('/login');
};
</script>

<template>
  <div class="login-page">
    <van-nav-bar
      title="用户登录"
      left-arrow
      @click-left="onClickLeft"
      fixed
      placeholder
    />
    
    <div class="login-container">
      <div class="login-logo">
        <div class="logo-mark">
          <van-icon name="service-o" size="40" />
        </div>
        <h2>RAG 智能问答</h2>
      </div>
      
      <van-form @submit="onSubmit" class="login-form">
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
        
        <div class="submit-btn">
          <van-button round block type="primary" native-type="submit" size="large">
            登录
          </van-button>
        </div>
        
        <div class="test-user-btn">
          <van-button round block type="default" size="large" @click="loginTestUser">
            测试用户登录
          </van-button>
        </div>
        
        <div class="register-link">
          还没有账号？<span @click="goToRegister">去注册</span>
        </div>
      </van-form>
    </div>
  </div>
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

<style scoped>
.login-page {
  background-color: var(--van-background);
}

.login-container {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.login-logo {
  margin: var(--van-padding-xl) 0;
  text-align: center;
}

.logo-mark {
  border-radius: 50%;
  background: var(--van-background);
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto var(--van-padding-md);
  color: var(--van-primary-color);
}

.login-logo h2 {
  color: var(--van-text-color);
  font-weight: var(--van-font-bold);
}

.login-form {
  width: 100%;
  padding: 0 var(--van-padding-md);
}

.submit-btn {
  margin: var(--van-padding-lg) var(--van-padding-md);
}

.test-user-btn {
  margin: 0 var(--van-padding-md);
}

.register-link {
  text-align: center;
  margin-top: var(--van-padding-lg);
  color: var(--van-text-color-3);
  font-size: var(--van-font-size-md);
}

.register-link span {
  color: var(--van-primary-color);
}
</style>

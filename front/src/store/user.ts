import axios from 'axios';
import { defineStore } from 'pinia';
import { computed, ref } from 'vue';
import type {
  LoginCredentials,
  OperationResult,
  RegistrationForm,
  UpdateUserPayload,
  UserInfo,
} from '../types';

const getCsrfToken = (): string => {
  const cookieValue = document.cookie
    .split('; ')
    .find((row) => row.startsWith('csrftoken='))
    ?.split('=')[1];
  return cookieValue || '';
};

export const useUserStore = defineStore('user', () => {
  const userInfo = ref<UserInfo | null>(null);
  const token = ref('');
  const isLogin = ref(false);
  const userBio = ref('这是我的个人简介');

  const getUserInfo = computed(() => userInfo.value);
  const getToken = computed(() => token.value);
  const getLoginStatus = computed(() => isLogin.value);
  const getUserBio = computed(() => userInfo.value?.bio || userBio.value);

  async function login(userData: LoginCredentials): Promise<OperationResult> {
    try {
      const TEST_USER = {
        username: 'test',
        password: '666666',
        token: 'test_token_for_unlogin',
        user: {
          id: 1,
          username: 'test',
          email: 'test@example.com',
          bio: '测试用户',
        } as UserInfo,
      };

      if (userData.username === TEST_USER.username && userData.password === TEST_USER.password) {
        localStorage.setItem('jwt_token', TEST_USER.token);
        userInfo.value = TEST_USER.user;
        token.value = TEST_USER.token;
        isLogin.value = true;
        return { success: true, message: '测试用户登录成功' };
      }

      const response = await axios.post<{
        user: UserInfo;
        token: string;
        message?: string;
        detail?: string;
      }>(
        '/user/login/',
        { username: userData.username, password: userData.password },
        { headers: { 'X-CSRFTOKEN': getCsrfToken() } },
      );

      if (response.status === 200) {
        localStorage.setItem('jwt_token', response.data.token);
        userInfo.value = response.data.user;
        token.value = response.data.token;
        isLogin.value = true;
        return { success: true, message: response.data.message };
      }
      return { success: false, message: response.data.detail || '登录失败' };
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: { non_field_errors?: string[] } } } };
      return {
        success: false,
        message: err.response?.data?.detail?.non_field_errors?.[0] || '登录请求失败，请稍后再试',
      };
    }
  }

  async function logout(): Promise<void> {
    // 先吊销本地凭据（立即生效，不依赖后端响应）。
    // 这样路由守卫在 router.push('/login') 时立刻看到无 token，不会把登录页重定向走。
    // 安全上也更稳：本地凭据先清，即使后端通知失败，本地已是登出态。
    const t = localStorage.getItem('jwt_token') || token.value;
    userInfo.value = null;
    token.value = '';
    isLogin.value = false;
    localStorage.removeItem('jwt_token');

    if (!t) return;

    try {
      await axios.post(
        '/user/logout/',
        {},
        {
          headers: { Authorization: `Bearer ${t}`, 'X-CSRFTOKEN': getCsrfToken() },
        },
      );
    } catch {
      // 后端通知失败不阻断登出，本地凭据已清
    }
  }

  async function getUserInfoDetail(): Promise<OperationResult<UserInfo>> {
    try {
      const t = localStorage.getItem('jwt_token') || token.value;
      if (!t) return { success: false, message: '未登录' };

      const response = await axios.get<{ data: UserInfo; message?: string; detail?: string }>(
        '/user/detail/',
        { headers: { Authorization: `Bearer ${t}`, 'X-CSRFTOKEN': getCsrfToken() } },
      );

      if (response.status === 200) {
        userInfo.value = response.data.data;
        return { success: true, message: response.data.message, data: response.data.data };
      }
      return { success: false, message: response.data.detail || '获取用户信息失败' };
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } };
      return {
        success: false,
        message: err.response?.data?.detail || '获取用户信息请求失败，请稍后再试',
      };
    }
  }

  async function updateUserInfo(userData: UpdateUserPayload): Promise<OperationResult> {
    try {
      const t = localStorage.getItem('jwt_token') || token.value;
      if (!t) return { success: false, message: '未登录' };

      const response = await axios.put<{
        user: UserInfo;
        token?: string;
        message?: string;
        detail?: string;
      }>('/user/update/', userData, {
        headers: {
          Authorization: `Bearer ${t}`,
          'X-CSRFTOKEN': getCsrfToken(),
          'Content-Type': 'application/json',
        },
      });

      if (response.status === 200) {
        userInfo.value = response.data.user;
        if (response.data.token) {
          token.value = response.data.token;
          localStorage.setItem('jwt_token', response.data.token);
        }
        return { success: true, message: response.data.message };
      }
      return { success: false, message: response.data.detail || '更新用户信息失败' };
    } catch (error: unknown) {
      const err = error as { response?: { data?: { message?: string; detail?: string } } };
      return {
        success: false,
        message:
          err.response?.data?.message ||
          err.response?.data?.detail ||
          '更新用户信息请求失败，请稍后再试',
      };
    }
  }

  async function updatePassword(
    oldPassword: string,
    newPassword: string,
  ): Promise<OperationResult> {
    try {
      const t = localStorage.getItem('jwt_token') || token.value;
      if (!t) return { success: false, message: '未登录' };

      const response = await axios.post<{ message?: string; detail?: string }>(
        '/user/change_password/',
        { old_password: oldPassword, new_password: newPassword },
        {
          headers: {
            Authorization: `Bearer ${t}`,
            'X-CSRFTOKEN': getCsrfToken(),
            'Content-Type': 'application/json',
          },
        },
      );

      if (response.status === 200) return { success: true, message: response.data.message };
      return { success: false, message: response.data.detail || '更新密码失败' };
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } };
      return {
        success: false,
        message: err.response?.data?.detail || '更新密码请求失败，请稍后再试',
      };
    }
  }

  /**
   * 从 localStorage 恢复登录态。
   * 刷新页面后 pinia 内存状态会重置，但 localStorage 里的 jwt_token 仍在。
   * 调用此方法把 token 同步回 pinia，使 UI（依据 isLogin）与路由守卫（依据 localStorage）保持一致。
   * 注意：仅恢复状态，不验证 token 有效性；token 过期的情况由后端 401 + axios 拦截器处理。
   */
  function restoreSession(): void {
    const t = localStorage.getItem('jwt_token');
    if (t) {
      token.value = t;
      isLogin.value = true;
    }
  }

  async function register(userData: RegistrationForm): Promise<OperationResult> {
    try {
      const response = await axios.post<{
        status: number;
        message?: string;
        user: UserInfo;
        token: string;
      }>(
        '/user/register/',
        {
          username: userData.username,
          email: userData.email,
          telephone: userData.telephone || '',
          password: userData.password,
          confirm_password: userData.confirm_password,
        },
        { headers: { 'X-CSRFTOKEN': getCsrfToken(), 'Content-Type': 'application/json' } },
      );

      if (response.data.status === 201 && response.data.token) {
        localStorage.setItem('jwt_token', response.data.token);
        userInfo.value = response.data.user;
        token.value = response.data.token;
        isLogin.value = true;
        return { success: true, message: response.data.message || '注册成功' };
      }
      return { success: false, message: response.data.message || '注册失败' };
    } catch (error: unknown) {
      const err = error as { response?: { data?: { message?: string; detail?: string } } };
      return {
        success: false,
        message:
          err.response?.data?.message || err.response?.data?.detail || '注册失败，请稍后重试',
      };
    }
  }

  return {
    userInfo,
    token,
    isLogin,
    userBio,
    getUserInfo,
    getToken,
    getLoginStatus,
    getUserBio,
    login,
    logout,
    getUserInfoDetail,
    updateUserInfo,
    updatePassword,
    register,
    restoreSession,
  };
});

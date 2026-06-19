<template>
  <div class="profile-page">
    <van-nav-bar
      title="个人信息"
      left-arrow
      @click-left="$router.back()"
      fixed
    />
    
    <div class="profile-container">
      <van-cell-group inset class="avatar-group">
        <van-cell title="头像" center is-link @click="showAvatarDialog">
          <template #right-icon>
            <div v-if="userInfo?.avatar" class="profile-avatar">
              <van-image round width="60" height="60" :src="`http://localhost:8001${userInfo.avatar}`" />
            </div>
            <div v-else class="profile-avatar-letter">
              {{ (userInfo?.username || '?')[0].toUpperCase() }}
            </div>
          </template>
        </van-cell>
      </van-cell-group>
      
      <van-cell-group inset class="info-group">
        <van-cell title="用户ID" :value="userInfo?.id || userInfo?.uuid || '未设置'" />
        <van-cell title="用户名" :value="userInfo?.username || '未设置'" is-link @click="showUsernameDialog" />
        <van-cell title="邮箱" :value="userInfo?.email || '未设置'" is-link @click="showEmailDialog" />
        <van-cell title="手机号" :value="userInfo?.telephone || '未设置'" is-link @click="showPhoneDialog" />
        <van-cell title="性别" :value="genderText || '未设置'" is-link @click="showGenderDialog" />
        <van-cell title="个人简介" :value="userBio || '暂无简介'" is-link @click="showBioDialog" />
        <van-cell title="注册时间" :value="createTimeText || '未设置'" />
        <van-cell title="最后登录时间" :value="lastLoginText || '未设置'" />
      </van-cell-group>
      
      <van-cell-group inset class="security-group">
        <van-cell title="修改密码" is-link @click="showPasswordConfirm" />
      </van-cell-group>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, h, onMounted } from 'vue';
import { useUserStore } from '../store/user';
import { showDialog, showToast, showLoadingToast, showSuccessToast, showFailToast, Dialog, RadioGroup, Radio, Field, Image, Uploader } from 'vant';
import { useRouter } from 'vue-router';
import axios from 'axios';
import { apiConfig } from '../config/api';

const router = useRouter();
const userStore = useUserStore();

// 初始化用户状态
onMounted(async () => {
  // 如果用户未登录，跳转到登录页面
  if (!userStore.getLoginStatus) {
    router.push('/login');
    return;
  }
  
  // 获取用户信息
  try {
    // 显示加载提示
    const loadingInstance = showLoadingToast({
      message: '加载中...',
      forbidClick: true,
      duration: 0
    });
    
    console.log('获取用户信息，当前token:', userStore.token);
    
    // 使用新的 getUserInfoDetail 方法
    const result = await userStore.getUserInfoDetail();
    
    console.log('获取用户信息结果:', result);
    console.log('当前用户信息:', userStore.userInfo);
    
    // 手动关闭加载提示
    loadingInstance.close();
    
    if (result.success) {
      // 不弹提示，静默加载
    } else {
      showFailToast(result.message || '获取用户信息失败');
    }
  } catch (error) {
    console.error('获取用户信息请求失败:', error);
    // 确保关闭加载提示
    showToast.clear();
    showToast.fail('获取用户信息失败');
  }
});

const userInfo = computed(() => userStore.userInfo);
const userId = computed(() => userStore.token ? userStore.token.substring(0, 5) : '');
const userBio = computed(() => userStore.userInfo?.bio || '暂无简介');

const genderText = computed(() => {
  const gender = userInfo.value?.gender;
  switch (gender) {
    case 1:
      return '男';
    case 2:
      return '女';
    case 3:
      return '其他';
    default:
      return '其他';
  }
});

const createTimeText = computed(() => {
  if (!userInfo.value?.create_time) return '未设置';
  const date = new Date(userInfo.value?.create_time);
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  });
});

const lastLoginText = computed(() => {
  if (!userInfo.value?.last_login) return '未设置';
  const date = new Date(userInfo.value?.last_login);
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  });
});

const showPasswordConfirm = () => {
  const oldPassword = ref('');
  const newPassword = ref('');
  const confirmPassword = ref('');
  
  showDialog({
    title: '修改密码',
    showCancelButton: true,
    message: h('div', { style: 'padding: var(--van-padding-sm) 0;' }, [
      h(Field, { modelValue: oldPassword.value, 'onUpdate:modelValue': (v) => oldPassword.value = v, type: 'password', label: '当前密码', placeholder: '请输入当前密码' }),
      h(Field, { modelValue: newPassword.value, 'onUpdate:modelValue': (v) => newPassword.value = v, type: 'password', label: '新密码', placeholder: '请输入新密码' }),
      h(Field, { modelValue: confirmPassword.value, 'onUpdate:modelValue': (v) => confirmPassword.value = v, type: 'password', label: '确认密码', placeholder: '请确认新密码' }),
    ]),
  }).then(async () => {
    // 点击确认按钮
    if (!oldPassword.value) {
      showToast('请输入当前密码');
      return;
    }
    
    if (!newPassword.value) {
      showToast('请输入新密码');
      return;
    }
    
    if (newPassword.value !== confirmPassword.value) {
      showToast('两次密码输入不一致');
      return;
    }
    
    try {
      // 显示加载提示
      const loadingInstance = showLoadingToast({
        message: '修改中...',
        forbidClick: true,
        duration: 0
      });
      
      // 调用API更新密码
      const result = await userStore.updatePassword(oldPassword.value, newPassword.value);
      
      // 关闭加载提示
      loadingInstance.close();
      
      if (result && result.success) {
        showSuccessToast('密码修改成功');
      } else {
        showFailToast((result && result.message) || '密码修改失败');
      }
    } catch (error) {
      console.error('修改密码失败:', error);
      showToast.clear();
      showToast.fail('密码修改失败');
    }
  }).catch(() => {
    // 点击取消按钮
  });
};

const showBioDialog = () => {
  const newBioValue = ref(userBio.value);
  
  showDialog({
    title: '修改个人简介',
    showCancelButton: true,
    confirmButtonText: '确认',
    message: h(Field, {
      modelValue: newBioValue.value,
      'onUpdate:modelValue': (v) => newBioValue.value = v,
      type: 'textarea',
      autosize: true,
      rows: 3,
      placeholder: '请输入个人简介',
      maxlength: 200,
    })
  }).then(async () => {
    // 点击确认按钮
    try {
      // 显示加载提示
      const loadingInstance = showLoadingToast({
        message: '保存中...',
        forbidClick: true,
        duration: 0
      });
      
      // 调用API更新个人简介
      const result = await userStore.updateUserInfo({ 
        username: userInfo.value?.username || '',
        email: userInfo.value?.email || '',
        telephone: userInfo.value?.telephone || '',
        gender: userInfo.value?.gender || 3,
        bio: newBioValue.value
      });
      
      // 关闭加载提示
      loadingInstance.close();
      
      if (result && result.success) {
        showSuccessToast('个人简介修改成功');
      } else {
        showFailToast((result && result.message) || '个人简介修改失败');
      }
    } catch (error) {
      console.error('更新个人简介失败:', error);
      showToast.clear();
      showToast.fail('个人简介修改失败');
    }
  }).catch(() => {
    // 点击取消按钮
  });
};

const showGenderDialog = () => {
  const selectedGender = ref(userInfo.value?.gender || 3);
  
  showDialog({
    title: '选择性别',
    message: h(RadioGroup, {
      modelValue: selectedGender.value,
      'onUpdate:modelValue': (v) => { selectedGender.value = v },
      direction: 'horizontal'
    }, {
      default: () => [
        h(Radio, { name: 1 }, { default: () => '男' }),
        h(Radio, { name: 2 }, { default: () => '女' }),
        h(Radio, { name: 3 }, { default: () => '其他' }),
      ]
    }),
    confirmButtonText: '确认',
    cancelButtonText: '取消',
    showCancelButton: true
  }).then(() => {
    // 点击确认按钮
    // 显示加载提示
    const loadingInstance = showLoadingToast({
      message: '保存中...',
      forbidClick: true,
      duration: 0
    });
    
    // 调用API更新性别
    userStore.updateUserInfo({ 
      username: userInfo.value?.username || '',
      email: userInfo.value?.email || '',
      telephone: userInfo.value?.telephone || '',
      gender: selectedGender.value,
      bio: userInfo.value?.bio || ''
    })
      .then((result) => {
        // 关闭加载提示
        loadingInstance.close();
        
        if (result && result.success) {
          showSuccessToast('性别修改成功');
        } else {
          showFailToast((result && result.message) || '性别修改失败');
        }
      })
      .catch((error) => {
        console.error('更新性别失败:', error);
        loadingInstance.close();
        showToast.fail('性别修改失败');
      });
  }).catch(() => {
    // 点击取消按钮
  });
};



const showUsernameDialog = () => {
  const newUsernameValue = ref(userInfo.value?.username || '');
  
  showDialog({
    title: '修改用户名',
    showCancelButton: true,
    confirmButtonText: '确认',
    message: h(Field, { modelValue: newUsernameValue.value, 'onUpdate:modelValue': (v) => newUsernameValue.value = v, label: '用户名', placeholder: '请输入用户名' })
  }).then(async () => {
    // 点击确认按钮
    try {
      // 显示加载提示
      const loadingInstance = showLoadingToast({
        message: '保存中...',
        forbidClick: true,
        duration: 0
      });
      
      // 调用API更新用户名
      const result = await userStore.updateUserInfo({ 
        username: newUsernameValue.value,
        email: userInfo.value?.email || '',
        telephone: userInfo.value?.telephone || '',
        gender: userInfo.value?.gender || 3,
        bio: userInfo.value?.bio || ''
      });
      
      // 关闭加载提示
      loadingInstance.close();
      
      if (result && result.success) {
        showSuccessToast('用户名修改成功');
      } else {
        showFailToast((result && result.message) || '用户名修改失败');
      }
    } catch (error) {
      console.error('更新用户名失败:', error);
      showToast.clear();
      showToast.fail('用户名修改失败');
    }
  }).catch(() => {
    // 点击取消按钮
  });
};

const showEmailDialog = () => {
  // 使用ref创建响应式变量
  const newEmailValue = ref(userInfo.value?.email || '');
  
  showDialog({
    title: '修改邮箱',
    showCancelButton: true,
    confirmButtonText: '确认',
    message: h(Field, { modelValue: newEmailValue.value, 'onUpdate:modelValue': (v) => newEmailValue.value = v, type: 'email', label: '邮箱', placeholder: '请输入邮箱' })
  }).then(async () => {
    // 点击确认按钮
    try {
      // 显示加载提示
      const loadingInstance = showLoadingToast({
        message: '保存中...',
        forbidClick: true,
        duration: 0
      });
      
      // 调用API更新邮箱
      const result = await userStore.updateUserInfo({ 
        username: userInfo.value?.username || '',
        email: newEmailValue.value,
        telephone: userInfo.value?.telephone || '',
        gender: userInfo.value?.gender || 3,
        bio: userInfo.value?.bio || ''
      });
      
      // 关闭加载提示
      loadingInstance.close();
      
      if (result && result.success) {
        showSuccessToast('邮箱修改成功');
      } else {
        showFailToast((result && result.message) || '邮箱修改失败');
      }
    } catch (error) {
      console.error('更新邮箱失败:', error);
      showToast.clear();
      showToast.fail('邮箱修改失败');
    }
  }).catch(() => {
    // 点击取消按钮
  });
};

const showPhoneDialog = () => {
  const newPhoneValue = ref(userInfo.value?.telephone || '');
  
  showDialog({
    title: '修改手机号',
    showCancelButton: true,
    confirmButtonText: '确认',
    message: h(Field, { modelValue: newPhoneValue.value, 'onUpdate:modelValue': (v) => newPhoneValue.value = v, type: 'tel', label: '手机号', placeholder: '请输入手机号', maxlength: 11 })
  }).then(async () => {
    // 点击确认按钮
    try {
      // 显示加载提示
      const loadingInstance = showLoadingToast({
        message: '保存中...',
        forbidClick: true,
        duration: 0
      });
      
      // 调用API更新手机号
      const result = await userStore.updateUserInfo({ 
        username: userInfo.value?.username || '',
        email: userInfo.value?.email || '',
        telephone: newPhoneValue.value,
        gender: userInfo.value?.gender || 3,
        bio: userInfo.value?.bio || ''
      });
      
      // 关闭加载提示
      loadingInstance.close();
      
      if (result && result.success) {
        showSuccessToast('手机号修改成功');
      } else {
        showFailToast((result && result.message) || '手机号修改失败');
      }
    } catch (error) {
      console.error('更新手机号失败:', error);
      showToast.clear();
      showToast.fail('手机号修改失败');
    }
  }).catch(() => {
    // 点击取消按钮
  });
};

const showAvatarDialog = () => {
  const selectedFile = ref(null);
  const previewUrl = ref(userInfo.value?.avatar ? `http://localhost:8001${userInfo.value.avatar}` : '');
  
  showDialog({
    title: '修改头像',
    showCancelButton: true,
    confirmButtonText: '确认上传',
    message: h('div', { style: 'text-align: center; padding: var(--van-padding-sm) 0;' }, [
      h(Image, { round: true, width: 100, height: 100, src: previewUrl.value, style: { marginBottom: '10px' } }),
      h(Uploader, {
        accept: 'image/*',
        maxCount: 1,
        onUpdateModelValue: (files) => {
          if (files.length > 0) {
            selectedFile.value = files[0].file || files[0];
            previewUrl.value = files[0].url || (files[0].file ? URL.createObjectURL(files[0].file) : '');
          }
        },
      }),
    ])
  }).then(async () => {
    // 点击确认按钮
    if (!selectedFile.value) {
      showToast('请选择要上传的图片');
      return;
    }
    
    try {
      // 显示加载提示
      const loadingInstance = showLoadingToast({
        message: '上传中...',
        forbidClick: true,
        duration: 0
      });
      
      // 创建FormData对象
      const formData = new FormData();
      formData.append('img', selectedFile.value);
      
      // 发送上传请求
      const response = await axios.post(`${apiConfig.userBaseURL}${apiConfig.endpoints.uploadFile}`, formData, {
        headers: {
          'Authorization': `Bearer ${userStore.token}`,
          'Content-Type': 'multipart/form-data'
        }
      });
      
      // 关闭加载提示
      loadingInstance.close();
      
      if (response.data && response.data.success) {
        // 更新用户信息
        await userStore.getUserInfoDetail();
        showSuccessToast('头像上传成功');
      } else {
        showFailToast((response.data && response.data.message) || '头像上传失败');
      }
    } catch (error) {
      console.error('上传头像失败:', error);
      showToast.clear();
      showToast.fail('头像上传失败');
    }
  }).catch(() => {
    // 点击取消按钮
  });
};
</script>

<style scoped>
.profile-page {
  min-height: 100vh;
  background-color: var(--van-background);
}

.profile-container {
  padding-top: 56px;
  padding-bottom: 20px;
}

.avatar-group,
.info-group,
.security-group {
  margin-top: 12px;
}

.avatar-group :deep(.van-cell),
.info-group :deep(.van-cell),
.security-group :deep(.van-cell) {
  background: var(--van-background-2);
  border-radius: 8px;
  margin-bottom: 6px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.08);
}

.profile-avatar-letter {
  width: 60px;
  height: 60px;
  border-radius: 50%;
  background: var(--van-background);
  color: var(--van-primary-color);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  
  font-weight: var(--van-font-bold);
  border: 2px solid var(--van-border-color);
}

.avatar-group :deep(.van-cell-group),
.security-group :deep(.van-cell-group) {
  border-radius: 8px;
}

.password-dialog .van-dialog__content {
  padding: var(--van-padding-lg);
}
</style>
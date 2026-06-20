import axios from 'axios';
import {
  Field,
  Radio,
  RadioGroup,
  showDialog,
  showFailToast,
  showLoadingToast,
  showSuccessToast,
  showToast,
  Uploader,
} from 'vant';
import { computed, h, ref } from 'vue';
import { apiConfig } from '../config/api';
import { useUserStore } from '../store/user';

/**
 * 个人信息编辑逻辑封装
 * 提取 Profile.vue 中 7 个重复的 showXxxDialog 函数
 */
export function useProfileEdit() {
  const userStore = useUserStore();
  const userInfo = computed(() => userStore.userInfo);

  // 构建完整的 updateUserInfo 参数（所有字段）
  const buildUpdatePayload = (overrides = {}) => ({
    username: userInfo.value?.username || '',
    email: userInfo.value?.email || '',
    telephone: userInfo.value?.telephone || '',
    gender: userInfo.value?.gender || 3,
    bio: userInfo.value?.bio || '',
    ...overrides,
  });

  // 通用：单字段编辑对话框
  const showFieldDialog = ({
    title,
    field,
    type = 'text',
    label,
    placeholder,
    maxlength,
    extraProps = {},
  }) => {
    const newValue = ref(userInfo.value?.[field] || '');

    showDialog({
      title,
      showCancelButton: true,
      confirmButtonText: '确认',
      message: () =>
        h(Field, {
          modelValue: newValue.value,
          'onUpdate:modelValue': (v) => {
            newValue.value = v;
          },
          type,
          label,
          placeholder,
          ...(maxlength ? { maxlength } : {}),
          ...extraProps,
        }),
    })
      .then(async () => {
        const loadingInstance = showLoadingToast({
          message: '保存中...',
          forbidClick: true,
          duration: 0,
        });
        try {
          const result = await userStore.updateUserInfo(
            buildUpdatePayload({ [field]: newValue.value }),
          );
          loadingInstance.close();
          if (result?.success) showSuccessToast(`${title}成功`);
          else showFailToast(result?.message || `${title}失败`);
        } catch {
          loadingInstance.close();
          showToast.clear();
          showToast.fail(`${title}失败`);
        }
      })
      .catch(() => {});
  };

  const editUsername = () =>
    showFieldDialog({
      title: '修改用户名',
      field: 'username',
      label: '用户名',
      placeholder: '请输入用户名',
    });

  const editEmail = () =>
    showFieldDialog({
      title: '修改邮箱',
      field: 'email',
      type: 'email',
      label: '邮箱',
      placeholder: '请输入邮箱',
    });

  const editPhone = () =>
    showFieldDialog({
      title: '修改手机号',
      field: 'telephone',
      type: 'tel',
      label: '手机号',
      placeholder: '请输入手机号',
      maxlength: 11,
    });

  const editBio = () =>
    showFieldDialog({
      title: '修改个人简介',
      field: 'bio',
      type: 'textarea',
      placeholder: '请输入个人简介',
      maxlength: 200,
      extraProps: { autosize: true, rows: 3 },
    });

  // 性别编辑（RadioGroup）
  const editGender = () => {
    const selectedGender = ref(userInfo.value?.gender || 3);

    showDialog({
      title: '选择性别',
      message: () =>
        h(
          RadioGroup,
          {
            modelValue: selectedGender.value,
            'onUpdate:modelValue': (v) => {
              selectedGender.value = v;
            },
            class: 'flex flex-col gap-3',
            direction: 'vertical',
          },
          {
            default: () => [
              h(Radio, { name: 1 }, { default: () => '男' }),
              h(Radio, { name: 2 }, { default: () => '女' }),
              h(Radio, { name: 3 }, { default: () => '其他' }),
            ],
          },
        ),
      confirmButtonText: '确认',
      cancelButtonText: '取消',
      showCancelButton: true,
    })
      .then(async () => {
        const loadingInstance = showLoadingToast({
          message: '保存中...',
          forbidClick: true,
          duration: 0,
        });
        try {
          const result = await userStore.updateUserInfo(
            buildUpdatePayload({ gender: selectedGender.value }),
          );
          loadingInstance.close();
          if (result?.success) showSuccessToast('性别修改成功');
          else showFailToast(result?.message || '性别修改失败');
        } catch {
          loadingInstance.close();
          showToast.fail('性别修改失败');
        }
      })
      .catch(() => {});
  };

  // 修改密码（3 个字段，调用 updatePassword API）
  const changePassword = () => {
    const oldPassword = ref('');
    const newPassword = ref('');
    const confirmPassword = ref('');

    showDialog({
      title: '修改密码',
      showCancelButton: true,
      message: () =>
        h('div', { style: 'padding: var(--van-padding-sm) 0;' }, [
          h(Field, {
            modelValue: oldPassword.value,
            'onUpdate:modelValue': (v) => {
              oldPassword.value = v;
            },
            type: 'password',
            label: '当前密码',
            placeholder: '请输入当前密码',
          }),
          h(Field, {
            modelValue: newPassword.value,
            'onUpdate:modelValue': (v) => {
              newPassword.value = v;
            },
            type: 'password',
            label: '新密码',
            placeholder: '请输入新密码',
          }),
          h(Field, {
            modelValue: confirmPassword.value,
            'onUpdate:modelValue': (v) => {
              confirmPassword.value = v;
            },
            type: 'password',
            label: '确认密码',
            placeholder: '请确认新密码',
          }),
        ]),
    })
      .then(async () => {
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

        const loadingInstance = showLoadingToast({
          message: '修改中...',
          forbidClick: true,
          duration: 0,
        });
        try {
          const result = await userStore.updatePassword(oldPassword.value, newPassword.value);
          loadingInstance.close();
          if (result?.success) showSuccessToast('密码修改成功');
          else showFailToast(result?.message || '密码修改失败');
        } catch {
          loadingInstance.close();
          showToast.clear();
          showToast.fail('密码修改失败');
        }
      })
      .catch(() => {});
  };

  // 头像上传
  const editAvatar = () => {
    const fileList = ref(
      userInfo.value?.avatar
        ? [{ url: `http://localhost:8001${userInfo.value.avatar}`, status: 'done' }]
        : [],
    );

    showDialog({
      title: '修改头像',
      showCancelButton: true,
      confirmButtonText: '确认上传',
      message: () =>
        h(Uploader, {
          modelValue: fileList.value,
          'onUpdate:modelValue': (files) => {
            fileList.value = files;
          },
          accept: 'image/*',
          maxCount: 1,
        }),
    })
      .then(async () => {
        if (fileList.value.length === 0) {
          showToast('请选择要上传的图片');
          return;
        }

        const fileItem = fileList.value[0];
        if (!fileItem.file) return; // 未选择新文件

        const loadingInstance = showLoadingToast({
          message: '上传中...',
          forbidClick: true,
          duration: 0,
        });
        try {
          const formData = new FormData();
          formData.append('img', fileItem.file);

          const response = await axios.post(
            `${apiConfig.userBaseURL}${apiConfig.endpoints.uploadFile}`,
            formData,
            {
              headers: {
                Authorization: `Bearer ${userStore.token}`,
                'Content-Type': 'multipart/form-data',
              },
            },
          );

          loadingInstance.close();
          if (response.data?.success) {
            await userStore.getUserInfoDetail();
            showSuccessToast('头像上传成功');
          } else {
            showFailToast(response.data?.message || '头像上传失败');
          }
        } catch {
          loadingInstance.close();
          showToast.clear();
          showToast.fail('头像上传失败');
        }
      })
      .catch(() => {});
  };

  return { editUsername, editEmail, editPhone, editBio, editGender, editAvatar, changePassword };
}

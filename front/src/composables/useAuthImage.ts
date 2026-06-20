import { useUserStore } from '../store/user';

type ImageMap = Record<string, string>;

export function useAuthImage(): {
  getAllImages: (md5: string) => Promise<ImageMap>;
  resolveImageUrls: (imagePaths: string[], imageMap: ImageMap) => string[];
} {
  const userStore = useUserStore();

  const getAllImages = async (md5: string): Promise<ImageMap> => {
    const token = userStore.token;
    if (!token) return {};

    try {
      const response = await fetch(`/knowledge/images/all/${md5}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) return {};
      const result = (await response.json()) as { code: number; data?: { images?: ImageMap } };
      if (result.code !== 200 || !result.data?.images) return {};
      return result.data.images;
    } catch {
      return {};
    }
  };

  const resolveImageUrls = (imagePaths: string[], imageMap: ImageMap): string[] => {
    return imagePaths
      .map((p) => {
        const basename = p
          .split('/')
          .pop()
          ?.replace(/\.[^.]+$/, '');
        const key = Object.keys(imageMap).find((k) => k.replace(/\.[^.]+$/, '') === basename);
        return key ? imageMap[key] : null;
      })
      .filter((url): url is string => url !== null);
  };

  return { getAllImages, resolveImageUrls };
}

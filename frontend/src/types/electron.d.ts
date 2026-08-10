export {};

declare global {
  interface Window {
    electronAPI?: {
      platform?: string;
      versions?: {
        node?: string;
        chrome?: string;
        electron?: string;
      };
      selectDirectory?: () => Promise<string | null>;
      showNotification?: (opts: { title?: string; body?: string; silent?: boolean }) => Promise<boolean>;
      openInFolder?: (filePath: string) => Promise<boolean>;
      openPath?: (dirPath: string) => Promise<boolean>;
    };
  }
}

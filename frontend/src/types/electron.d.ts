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
    };
  }
}

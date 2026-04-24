"use client";

import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import clsx from "clsx";
import mammoth from "mammoth";
import {
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  FileText,
  Folder,
  GripVertical,
  Loader2,
  PanelRightClose,
  RefreshCw,
} from "lucide-react";
import { MarkdownBody } from "@/components/MarkdownBody";

const LS_PANEL_W = "koraku.workspace.panelWidthPx";
const LS_TREE_W = "koraku.workspace.treeWidthPx";
const LS_TREE_COLLAPSED = "koraku.workspace.treeCollapsed";

const PANEL_MIN = 300;
const PANEL_DEFAULT = 560;
const TREE_MIN = 112;
const TREE_DEFAULT = 200;
const TREE_MAX_FIXED = 440;

function clamp(n: number, lo: number, hi: number) {
  return Math.min(hi, Math.max(lo, n));
}

function readNumLs(key: string, fallback: number) {
  if (typeof window === "undefined") return fallback;
  const raw = localStorage.getItem(key);
  const n = raw ? parseInt(raw, 10) : NaN;
  return Number.isFinite(n) ? n : fallback;
}

function readBoolLs(key: string, fallback: boolean) {
  if (typeof window === "undefined") return fallback;
  const raw = localStorage.getItem(key);
  if (raw === "1" || raw === "true") return true;
  if (raw === "0" || raw === "false") return false;
  return fallback;
}

type TreeEntry = {
  name: string;
  path: string;
};

type TreeResponse = {
  root: string;
  path: string;
  files: TreeEntry[];
  directories: TreeEntry[];
};

type FilePreview =
  | { kind: "markdown"; path: string; content: string; truncated: boolean }
  | { kind: "text"; path: string; content: string; truncated: boolean }
  | { kind: "pdf"; path: string; blobUrl: string }
  | { kind: "docx"; path: string; html: string };

function joinRel(parent: string, name: string): string {
  const p = parent.trim();
  const n = name.trim();
  if (!p) return n;
  if (!n) return p;
  return `${p}/${n}`;
}

function extensionOf(rel: string): string {
  const base = rel.split("/").pop() ?? rel;
  const i = base.lastIndexOf(".");
  return i >= 0 ? base.slice(i).toLowerCase() : "";
}

function isMarkdownExt(ext: string): boolean {
  return ext === ".md" || ext === ".markdown" || ext === ".mdx";
}

function isTextLikeExt(ext: string): boolean {
  if (!ext) return true;
  const text = new Set([
    ".txt",
    ".log",
    ".csv",
    ".tsv",
    ".json",
    ".jsonl",
    ".ndjson",
    ".tsx",
    ".ts",
    ".mts",
    ".cts",
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
    ".html",
    ".htm",
    ".css",
    ".scss",
    ".sass",
    ".less",
    ".xml",
    ".svg",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".env",
    ".sh",
    ".bash",
    ".zsh",
    ".py",
    ".rs",
    ".go",
    ".java",
    ".kt",
    ".swift",
    ".rb",
    ".php",
    ".sql",
    ".graphql",
    ".vue",
    ".svelte",
    ".dockerfile",
    ".gitignore",
    ".mdc",
  ]);
  return text.has(ext);
}

/**
 * Cloud workspace column — docks to the right of chat (same chrome idea as ``Sidebar``),
 * not a modal overlay.
 */
export function WorkspacePanel({
  visible,
  onClose,
  serverSessionId,
}: {
  visible: boolean;
  onClose: () => void;
  serverSessionId: string | null;
}) {
  const innerSplitRef = useRef<HTMLDivElement>(null);

  const [panelWidthPx, setPanelWidthPx] = useState(PANEL_DEFAULT);
  const [treeWidthPx, setTreeWidthPx] = useState(TREE_DEFAULT);
  const [treeCollapsed, setTreeCollapsed] = useState(false);
  const [hydrated, setHydrated] = useState(false);
  const [resizeMode, setResizeMode] = useState<null | "panel" | "tree">(null);

  const [relPath, setRelPath] = useState("");
  const [tree, setTree] = useState<TreeResponse | null>(null);
  const [fileRel, setFileRel] = useState<string | null>(null);
  const [filePreview, setFilePreview] = useState<FilePreview | null>(null);
  const [loadingTree, setLoadingTree] = useState(false);
  const [loadingFile, setLoadingFile] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useLayoutEffect(() => {
    setPanelWidthPx(clamp(readNumLs(LS_PANEL_W, PANEL_DEFAULT), PANEL_MIN, 2000));
    setTreeWidthPx(clamp(readNumLs(LS_TREE_W, TREE_DEFAULT), TREE_MIN, TREE_MAX_FIXED));
    setTreeCollapsed(readBoolLs(LS_TREE_COLLAPSED, false));
    setHydrated(true);
  }, []);

  const maxPanelWidth = useCallback(() => {
    if (typeof window === "undefined") return 900;
    return clamp(window.innerWidth - 320, PANEL_MIN, 1200);
  }, []);

  const maxTreeWidth = useCallback(() => {
    const el = innerSplitRef.current;
    const inner = el?.clientWidth ?? 400;
    return clamp(Math.floor(inner * 0.62), TREE_MIN, TREE_MAX_FIXED);
  }, []);

  const startPanelResize = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      setResizeMode("panel");
      const startX = e.clientX;
      const startW = panelWidthPx;
      const onMove = (ev: MouseEvent) => {
        const next = clamp(
          Math.round(startW + ev.clientX - startX),
          PANEL_MIN,
          maxPanelWidth(),
        );
        setPanelWidthPx(next);
      };
      const onUp = () => {
        setResizeMode(null);
        window.removeEventListener("mousemove", onMove);
        window.removeEventListener("mouseup", onUp);
        setPanelWidthPx((w) => {
          localStorage.setItem(LS_PANEL_W, String(w));
          return w;
        });
      };
      window.addEventListener("mousemove", onMove);
      window.addEventListener("mouseup", onUp);
    },
    [maxPanelWidth, panelWidthPx],
  );

  const startTreeResize = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      if (treeCollapsed) return;
      setResizeMode("tree");
      const startX = e.clientX;
      const startW = treeWidthPx;
      const onMove = (ev: MouseEvent) => {
        const next = clamp(
          Math.round(startW + ev.clientX - startX),
          TREE_MIN,
          maxTreeWidth(),
        );
        setTreeWidthPx(next);
      };
      const onUp = () => {
        setResizeMode(null);
        window.removeEventListener("mousemove", onMove);
        window.removeEventListener("mouseup", onUp);
        setTreeWidthPx((w) => {
          localStorage.setItem(LS_TREE_W, String(w));
          return w;
        });
      };
      window.addEventListener("mousemove", onMove);
      window.addEventListener("mouseup", onUp);
    },
    [maxTreeWidth, treeCollapsed, treeWidthPx],
  );

  const collapseTree = useCallback(() => {
    setTreeCollapsed(true);
    localStorage.setItem(LS_TREE_COLLAPSED, "1");
  }, []);

  const expandTree = useCallback(() => {
    setTreeCollapsed(false);
    localStorage.setItem(LS_TREE_COLLAPSED, "0");
  }, []);

  useEffect(() => {
    if (!visible) return;
    const onResize = () => {
      setPanelWidthPx((w) => clamp(w, PANEL_MIN, maxPanelWidth()));
      setTreeWidthPx((tw) => clamp(tw, TREE_MIN, maxTreeWidth()));
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [visible, maxPanelWidth, maxTreeWidth]);

  const loadTree = useCallback(async () => {
    if (!serverSessionId) return;
    setLoadingTree(true);
    setError(null);
    try {
      const q = new URLSearchParams({
        session_id: serverSessionId,
        path: relPath,
      });
      const res = await fetch(`/koraku-api/api/workspace/tree?${q}`);
      const text = await res.text();
      if (!res.ok) {
        setTree(null);
        setError(text.slice(0, 400) || res.statusText);
        return;
      }
      setTree(JSON.parse(text) as TreeResponse);
    } catch (e) {
      setTree(null);
      setError(String((e as Error)?.message || e));
    } finally {
      setLoadingTree(false);
    }
  }, [relPath, serverSessionId]);

  const loadFile = useCallback(
    async (rel: string) => {
      if (!serverSessionId) return;
      setLoadingFile(true);
      setError(null);
      setFileRel(rel);
      setFilePreview(null);
      const ext = extensionOf(rel);
      try {
        if (ext === ".pdf" || ext === ".docx") {
          const q = new URLSearchParams({
            session_id: serverSessionId,
            path: rel,
          });
          const res = await fetch(`/koraku-api/api/workspace/file/blob?${q}`);
          if (!res.ok) {
            const t = await res.text();
            setError(t.slice(0, 400) || res.statusText);
            return;
          }
          const buf = await res.arrayBuffer();
          if (ext === ".pdf") {
            const blob = new Blob([buf], { type: "application/pdf" });
            const blobUrl = URL.createObjectURL(blob);
            setFilePreview({ kind: "pdf", path: rel, blobUrl });
          } else {
            const conv = await mammoth.convertToHtml({ arrayBuffer: buf });
            setFilePreview({ kind: "docx", path: rel, html: conv.value });
          }
          return;
        }

        const q = new URLSearchParams({
          session_id: serverSessionId,
          path: rel,
        });
        const res = await fetch(`/koraku-api/api/workspace/file?${q}`);
        const text = await res.text();
        if (!res.ok) {
          setError(text.slice(0, 400) || res.statusText);
          return;
        }
        const data = JSON.parse(text) as {
          path: string;
          content: string;
          truncated: boolean;
        };
        const kind = isMarkdownExt(ext) ? "markdown" : "text";
        setFilePreview({
          kind,
          path: data.path,
          content: data.content,
          truncated: data.truncated,
        });
      } catch (e) {
        setError(String((e as Error)?.message || e));
      } finally {
        setLoadingFile(false);
      }
    },
    [serverSessionId],
  );

  useEffect(() => {
    if (!filePreview || filePreview.kind !== "pdf") return;
    const u = filePreview.blobUrl;
    return () => URL.revokeObjectURL(u);
  }, [filePreview]);

  useEffect(() => {
    if (visible) {
      setRelPath("");
      setFileRel(null);
      setFilePreview(null);
      setError(null);
    }
  }, [visible]);

  useEffect(() => {
    if (!visible || !serverSessionId) return;
    void loadTree();
  }, [visible, serverSessionId, relPath, loadTree]);

  const segments = relPath ? relPath.split("/").filter(Boolean) : [];

  const panelW = hydrated ? panelWidthPx : PANEL_DEFAULT;

  return (
    <aside
      style={{ width: visible ? panelW : 0 }}
      className={clsx(
        "relative flex h-full min-h-0 shrink-0 flex-col overflow-hidden border-l border-neutral-200/90 bg-[#fbfbfc] ease-out",
        resizeMode === "panel" ? "duration-0" : "duration-200 transition-[width]",
        "shadow-[inset_1px_0_0_rgb(255_255_255_/_0.6)]",
        visible ? "min-w-[300px]" : "min-w-0 border-l-0",
      )}
      aria-hidden={!visible}
    >
      {visible ? (
        <button
          type="button"
          aria-label="Resize workspace panel"
          onMouseDown={startPanelResize}
          className={clsx(
            "absolute left-0 top-0 z-20 h-full w-3 -translate-x-1/2 cursor-col-resize touch-none",
            "bg-transparent hover:bg-neutral-900/[0.06] active:bg-neutral-900/[0.1]",
            resizeMode === "panel" && "bg-neutral-900/10",
          )}
        />
      ) : null}
      <div
        className={clsx(
          "flex h-full min-h-0 w-full flex-col",
          visible ? "min-w-[300px]" : "min-w-0",
          !visible && "pointer-events-none opacity-0",
        )}
      >
        <header className="flex shrink-0 items-center justify-between gap-2 border-b border-neutral-200/60 bg-[#f7f7f7] px-3 py-2.5">
          <div className="min-w-0">
            <p className="text-[10px] font-bold uppercase tracking-wider text-neutral-400">
              Session
            </p>
            <h2 className="truncate text-[13px] font-semibold text-koraku-ink">
              Cloud workspace
            </h2>
          </div>
          <div className="flex shrink-0 items-center gap-0.5">
            <button
              type="button"
              onClick={() => void loadTree()}
              disabled={!serverSessionId || loadingTree}
              className="rounded-lg p-2 text-neutral-500 hover:bg-white/80 disabled:opacity-40"
              title="Refresh"
            >
              <RefreshCw
                className={clsx("h-4 w-4", loadingTree && "animate-spin")}
              />
            </button>
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg p-2 text-neutral-500 hover:bg-white/80"
              title="Hide workspace"
            >
              <PanelRightClose className="h-4 w-4" />
            </button>
          </div>
        </header>

        {!serverSessionId ? (
          <div className="flex flex-1 flex-col items-center justify-center gap-2 px-5 text-center text-[13px] text-neutral-500">
            <p>
              Send a message in <strong>Cloud</strong> mode first.
            </p>
            <p className="text-xs text-neutral-400">
              Your Blaxel session folder appears here after the first reply streams.
            </p>
          </div>
        ) : (
          <>
            <nav className="flex shrink-0 items-center gap-1 border-b border-neutral-100 bg-white/60 px-2 py-1.5 text-[11px] text-neutral-500">
              <div className="flex min-w-0 flex-1 flex-wrap items-center gap-0.5">
                <span className="flex items-center">
                  <button
                    type="button"
                    className="max-w-[100px] truncate rounded px-1 py-0.5 hover:bg-neutral-100 hover:text-koraku-ink"
                    onClick={() => {
                      setRelPath("");
                      setFileRel(null);
                      setFilePreview(null);
                    }}
                  >
                    root
                  </button>
                </span>
                {segments.map((seg, i) => {
                  const cum = segments.slice(0, i + 1).join("/");
                  return (
                    <span key={cum} className="flex items-center">
                      <ChevronRight className="mx-0.5 h-3 w-3 shrink-0 opacity-40" />
                      <button
                        type="button"
                        className="max-w-[100px] truncate rounded px-1 py-0.5 hover:bg-neutral-100 hover:text-koraku-ink"
                        onClick={() => {
                          setRelPath(cum);
                          setFileRel(null);
                          setFilePreview(null);
                        }}
                      >
                        {seg}
                      </button>
                    </span>
                  );
                })}
              </div>
              {!treeCollapsed ? (
                <button
                  type="button"
                  onClick={collapseTree}
                  title="Collapse file tree"
                  className="shrink-0 rounded-md p-1.5 text-neutral-400 transition hover:bg-neutral-100 hover:text-neutral-700"
                >
                  <ChevronsLeft className="h-4 w-4" strokeWidth={1.5} aria-hidden />
                </button>
              ) : null}
            </nav>

            <div ref={innerSplitRef} className="flex min-h-0 flex-1 flex-row">
              {treeCollapsed ? (
                <div className="flex w-11 shrink-0 flex-col items-center border-r border-neutral-200/80 bg-neutral-100/50 py-2">
                  <button
                    type="button"
                    onClick={expandTree}
                    title="Show file tree"
                    className="rounded-lg p-2 text-neutral-500 transition hover:bg-white hover:text-neutral-900"
                  >
                    <ChevronsRight className="h-4 w-4" strokeWidth={1.5} aria-hidden />
                  </button>
                </div>
              ) : (
                <>
                  <div
                    style={{ width: treeWidthPx }}
                    className="flex min-h-0 min-w-0 shrink-0 flex-col bg-white/50"
                  >
                {error && !tree ? (
                  <p className="p-2.5 text-xs text-red-600">{error}</p>
                ) : null}
                <ul className="min-h-0 flex-1 overflow-y-auto py-1">
                  {relPath ? (
                    <li>
                      <button
                        type="button"
                        className="flex w-full items-center gap-2 px-2.5 py-1.5 text-left text-[12px] text-neutral-600 hover:bg-neutral-100/80"
                        onClick={() => {
                          const parts = relPath.split("/").filter(Boolean);
                          parts.pop();
                          setRelPath(parts.join("/"));
                          setFileRel(null);
                          setFilePreview(null);
                        }}
                      >
                        <span className="text-neutral-400">‥</span>
                        <span>Parent</span>
                      </button>
                    </li>
                  ) : null}
                  {(tree?.directories ?? []).map((d) => (
                    <li key={`d:${d.path}`}>
                      <button
                        type="button"
                        className="flex w-full items-center gap-2 px-2.5 py-1.5 text-left text-[12px] hover:bg-neutral-100/80"
                        onClick={() => {
                          setRelPath(joinRel(relPath, d.name));
                          setFileRel(null);
                          setFilePreview(null);
                        }}
                      >
                        <Folder className="h-3.5 w-3.5 shrink-0 text-amber-600/90" />
                        <span className="truncate font-medium text-koraku-ink">
                          {d.name}
                        </span>
                      </button>
                    </li>
                  ))}
                  {(tree?.files ?? []).map((f) => {
                    const full = joinRel(relPath, f.name);
                    const ext = extensionOf(f.name);
                    const previewable =
                      ext === ".pdf" ||
                      ext === ".docx" ||
                      isMarkdownExt(ext) ||
                      isTextLikeExt(ext);
                    return (
                      <li key={`f:${f.path}`}>
                        <button
                          type="button"
                          className={clsx(
                            "flex w-full items-center gap-2 px-2.5 py-1.5 text-left text-[12px] hover:bg-neutral-100/80",
                            fileRel === full && "bg-neutral-100/90",
                            !previewable && "opacity-60",
                          )}
                          title={
                            previewable
                              ? undefined
                              : "No in-panel preview for this type yet"
                          }
                          onClick={() =>
                            previewable ? void loadFile(full) : undefined
                          }
                          disabled={!previewable}
                        >
                          <FileText className="h-3.5 w-3.5 shrink-0 text-neutral-400" />
                          <span className="truncate text-koraku-ink">{f.name}</span>
                        </button>
                      </li>
                    );
                  })}
                  {!loadingTree &&
                  !(tree?.directories?.length) &&
                  !(tree?.files?.length) ? (
                    <li className="px-3 py-8 text-center text-xs text-neutral-400">
                      Empty folder
                    </li>
                  ) : null}
                  {loadingTree ? (
                    <li className="flex items-center justify-center gap-2 py-10 text-xs text-neutral-400">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Loading…
                    </li>
                  ) : null}
                </ul>
                  </div>
                  <div
                    role="separator"
                    aria-orientation="vertical"
                    aria-label="Resize file tree"
                    onMouseDown={startTreeResize}
                    className={clsx(
                      "group relative z-10 w-3 shrink-0 cursor-col-resize touch-none",
                      resizeMode === "tree" ? "bg-neutral-300/50" : "bg-transparent",
                    )}
                  >
                    <div
                      className={clsx(
                        "pointer-events-none absolute inset-y-1 left-1/2 w-px -translate-x-1/2 rounded-full bg-neutral-200/90 transition-colors",
                        "group-hover:bg-neutral-400",
                        resizeMode === "tree" && "bg-neutral-500",
                      )}
                    />
                    <div className="pointer-events-none flex h-full items-center justify-center">
                      <GripVertical
                        className="h-8 w-4 rounded-md text-neutral-400 opacity-0 transition-opacity group-hover:opacity-80"
                        strokeWidth={1.5}
                        aria-hidden
                      />
                    </div>
                  </div>
                </>
              )}

              <div className="flex min-h-0 min-w-0 flex-1 flex-col bg-neutral-50/50">
                {error && tree ? (
                  <p className="shrink-0 border-b border-red-100 bg-red-50/90 px-2.5 py-1.5 text-xs text-red-700">
                    {error}
                  </p>
                ) : null}
                {!fileRel ? (
                  <p className="m-auto max-w-[12rem] text-center text-xs text-neutral-400">
                    Select a file to preview
                  </p>
                ) : loadingFile ? (
                  <div className="m-auto flex items-center gap-2 text-xs text-neutral-400">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Loading…
                  </div>
                ) : filePreview ? (
                  <div className="flex min-h-0 flex-1 flex-col">
                    <div className="shrink-0 border-b border-neutral-200/80 bg-white/95 px-2.5 py-1.5 text-[10px] text-neutral-500">
                      <span className="break-all">{filePreview.path}</span>
                      {"truncated" in filePreview && filePreview.truncated ? (
                        <span className="ml-1.5 text-amber-700">(truncated)</span>
                      ) : null}
                    </div>
                    {filePreview.kind === "markdown" ? (
                      <div className="min-h-0 flex-1 overflow-auto px-2 py-2">
                        <MarkdownBody source={filePreview.content} />
                      </div>
                    ) : null}
                    {filePreview.kind === "text" ? (
                      <pre className="min-h-0 flex-1 overflow-auto p-2.5 font-mono text-[11px] leading-relaxed text-neutral-800">
                        {filePreview.content}
                      </pre>
                    ) : null}
                    {filePreview.kind === "pdf" ? (
                      <iframe
                        title="PDF preview"
                        src={filePreview.blobUrl}
                        className="min-h-0 w-full flex-1 border-0 bg-neutral-200/40"
                      />
                    ) : null}
                    {filePreview.kind === "docx" ? (
                      <div
                        className="koraku-md min-h-0 flex-1 overflow-auto break-words px-3 py-2 text-[13px] leading-relaxed text-neutral-800"
                        // mammoth output is constrained doc HTML; workspace files are user-owned.
                        dangerouslySetInnerHTML={{ __html: filePreview.html }}
                      />
                    ) : null}
                  </div>
                ) : null}
              </div>
            </div>
          </>
        )}
      </div>
    </aside>
  );
}

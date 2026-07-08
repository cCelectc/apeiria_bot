export interface Plugin {
  name: string;
  source: string;
  enabled: boolean;
  path_or_module: string;
  module: string;
  display_name: string | null;
  description: string | null;
  usage: string | null;
  type: string | null;
  homepage: string | null;
  supported_adapters: string[] | null;
  can_disable: boolean;
  can_uninstall: boolean;
  installed_version: string | null;
  depends_on: string[];
  depended_by: string[];
}

export interface Adapter {
  name: string;
  source: string;
  enabled: boolean;
  module_name: string;
  installed_version: string | null;
}

export interface PluginVersions {
  versions: string[];
}

export interface UpdateInfo {
  installed: string | null;
  latest: string | null;
  update_available: boolean;
}

export interface CheckUpdatesResult {
  updates: Record<string, UpdateInfo>;
}

export interface ConfigContract {
  namespace: string | null;
  is_scoped: boolean;
  owner_kind: "plugin" | "adapter" | "nonebot" | "apeiria";
  owner_id: string;
  source: "pydantic" | "extra_only" | "none";
  fields: FieldNode[];
  json_schema: Record<string, unknown>;
}

export type FieldNode =
  PrimitiveField | ObjectField | ArrayField | MapField | AnyField;

export interface PrimitiveField {
  kind: "primitive";
  key: string;
  label: string;
  description: string;
  type: "str" | "int" | "float" | "bool" | "enum" | "literal";
  default: unknown;
  required: boolean;
  secret: boolean;
  choices?: { value: string; label: string }[];
  order: number;
  immutable?: boolean;
}

export interface ObjectField {
  kind: "object";
  key: string;
  label: string;
  description: string;
  children: FieldNode[];
  default: Record<string, unknown> | null;
  order: number;
  immutable?: boolean;
}

export interface ArrayField {
  kind: "array";
  key: string;
  label: string;
  description: string;
  item_schema: FieldNode | null;
  default: unknown[] | null;
  order: number;
  immutable?: boolean;
}

export interface MapField {
  kind: "map";
  key: string;
  label: string;
  description: string;
  key_type: string;
  value_schema: FieldNode | null;
  order: number;
  immutable?: boolean;
}

export interface AnyField {
  kind: "any";
  key: string;
  label: string;
  description: string;
  default: unknown;
  order: number;
  immutable?: boolean;
}

export interface StoreTag {
  label: string;
  color: string;
}

export interface StoreItem {
  name: string;
  version: string;
  description: string;
  author: string;
  homepage: string;
  pypi_name: string;
  module_names: string[];
  supported_adapters: string[] | null;
  installed_version: string | null;
  type: string;
  tags: StoreTag[];
  is_official: boolean;
  time: string;
}

export interface StoreSearchResult {
  results: StoreItem[];
  total: number;
}

export interface LogRecord {
  ts: number;
  level: string;
  name: string;
  message: string;
}

export interface StatusInfo {
  uptime: number;
  plugin_count: number;
  adapters: string[];
}

export interface LogHistory {
  items: LogRecord[];
  total: number;
  page: number;
  size: number;
}

export interface LoginResponse {
  token: string;
  username: string;
}

export interface InstallTaskResponse {
  task_id: string;
}

export interface TaskEvent {
  type: "output" | "done" | "error";
  text?: string;
  ok?: boolean;
  name?: string;
  message?: string;
}

export type WebchatSegment =
  | { type: "text"; text: string }
  | { type: "image"; url: string }
  | { type: "raw"; seg_type: string; data: Record<string, unknown> };

export interface WebchatMessage {
  id: string;
  role: "user" | "bot";
  segments: WebchatSegment[];
  time: string;
  session_id: string;
  user_id?: string | null;
}

export interface WebchatIdentity {
  user_id?: string;
  scene_type?: "private" | "group";
  scene_id?: string;
}

export type WebchatInFrame =
  | {
      type: "message";
      text: string;
      image?: string;
      identity?: WebchatIdentity;
    }
  | { type: "clear" }
  | { type: "delete"; message_id: string }
  | { type: "switch"; identity: WebchatIdentity };

export type WebchatOutFrame =
  | { type: "history"; session_id: string; messages: WebchatMessage[] }
  | { type: "message"; message: WebchatMessage }
  | { type: "cleared"; session_id: string }
  | { type: "deleted"; message_id: string }
  | { type: "error"; code: string; message: string };

export interface WebchatSimUser {
  id: string;
  name: string;
}

export interface WebchatSimGroup {
  id: string;
  name: string;
}

export interface WebchatConversation {
  key: string;
  type: "private" | "group";
  name: string;
  groupId?: string;
}

export interface AccessRule {
  id: number;
  subject_type: "user" | "group";
  subject_id: string;
  plugin_name: string | null;
  action: "allow" | "deny";
  priority: number;
}

export interface AccessRulesList {
  rules: AccessRule[];
}

export interface AccessPreviewResult {
  action: "allow" | "deny";
  matched_rule_id: number | null;
  matched_rule: AccessRule | null;
}

export interface AccessSubjectsResult {
  subjects: { id: string; type: string }[];
}

export interface UpdateStatusResponse {
  branch: string;
  commit_hash: string;
  commit_message: string;
  is_dirty: boolean;
  dirty_files: string[];
  available_branches: string[];
  available_tags: string[];
}

export interface UpdatePreviewResponse {
  ref: string;
  type: string;
  remote_commit_hash: string;
  remote_commit_message: string;
  commits_behind: number;
  commits: GitCommit[];
}

export interface GitCommit {
  hash: string;
  message: string;
  author: string;
  date: string;
}

export interface UpdateEvent {
  stage: string;
  line: string;
}

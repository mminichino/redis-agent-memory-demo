/** Stored in Redis on the account hash as JSON under `settings`. Add fields here and merge in `mergeUserSettings`. */
export type UserSettings = {
  show_tool_responses: boolean;
};

export const defaultUserSettings: UserSettings = {
  show_tool_responses: false
};

export type Account = {
  user_id: string;
  first_name: string;
  last_name: string;
  email?: string;
  is_admin: boolean;
  created_at: string;
  updated_at: string;
  settings: UserSettings;
};

export type Session = {
  token: string;
  user_id: string;
  created_at: string;
};

export type ChatEvent =
  | { type: "status"; message: string }
  | {
      type: "message";
      role: string;
      content: string;
      raw: unknown;
      /** Elapsed ms since stream segment anchor (set after prior assistant/tool_result); omitted for tool-role payloads. */
      runtime_ms?: number;
    }
  | {
      type: "tool_call";
      name: string;
      args: string;
      started_at: number;
    }
  | {
      type: "tool_result";
      name: string;
      /** Elapsed ms since segment anchor (covers tool execution; excludes hidden tool message line). */
      runtime_ms: number;
      content: string;
    }
  | { type: "error"; message: string }
  | { type: "done" };

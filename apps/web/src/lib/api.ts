const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/* Một request treo thì UI treo theo — `SessionProvider` kẹt `loading` vĩnh
   viễn là ca đã xảy ra. Không ai chờ một lượt đọc quá chừng này. */
const API_TIMEOUT_MS = 30_000;

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type ValidationIssue = { msg: string; loc?: (string | number)[] };

/**
 * Lỗi 422 của FastAPI có TÊN TRƯỜNG trong `loc`, và bỏ nó đi là bỏ đi toàn bộ
 * thông tin hữu ích: ba trường trống cùng lúc cho ra ba dòng "String should have
 * at least 1 character" giống hệt nhau, không dòng nào nói trường nào.
 *
 * `loc` là ["body", "source_url"], nên phần tử cuối là cái cần.
 */
function issueText(issue: ValidationIssue): string {
  const field = issue.loc?.filter((part) => part !== "body").at(-1);
  return field ? `${field}: ${issue.msg}` : issue.msg;
}

async function parseError(response: Response): Promise<string> {
  try {
    const data = (await response.json()) as { detail?: string | ValidationIssue[] };
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.detail)) return data.detail.map(issueText).join(" · ");
  } catch {
    /* ignore */
  }
  return response.statusText || "Request failed";
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit & { token?: string } = {},
): Promise<T> {
  const { token, headers, signal, ...rest } = options;
  const method = (rest.method ?? "GET").toUpperCase();
  // GET đang bay mà component khác hỏi cùng URL + token thì đi ké — dashboard
  // và tour đọc `/me`/profile cùng lúc là ca gặp mỗi ngày. Chỉ GET không
  // signal riêng: POST trùng là ghi trùng, còn signal của người gọi phải huỷ
  // độc lập chứ không chờ ké.
  if (method === "GET" && !signal) {
    const key = `${path} ${token ?? ""}`;
    const flying = inflight.get(key);
    if (flying) return flying as Promise<T>;
    const done = request<T>(path, token, headers, rest, undefined).finally(() => {
      if (inflight.get(key) === done) inflight.delete(key);
    });
    inflight.set(key, done);
    return done;
  }
  return request<T>(path, token, headers, rest, signal ?? undefined);
}

const inflight = new Map<string, Promise<unknown>>();

async function request<T>(
  path: string,
  token: string | undefined,
  headers: HeadersInit | undefined,
  rest: Omit<RequestInit, "headers" | "signal">,
  signal: AbortSignal | undefined,
): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...rest,
    signal: signal ?? AbortSignal.timeout(API_TIMEOUT_MS),
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...headers,
    },
  });

  if (!response.ok) {
    throw new ApiError(await parseError(response), response.status);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

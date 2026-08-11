const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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
  const { token, headers, ...rest } = options;
  const response = await fetch(`${API_BASE}${path}`, {
    ...rest,
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

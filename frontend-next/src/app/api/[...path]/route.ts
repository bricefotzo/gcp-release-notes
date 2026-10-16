import { NextRequest, NextResponse } from "next/server";

export async function GET(request: NextRequest, props: { params: Promise<{ path: string[] }> }) {
  const params = await props.params;
  return handle(request, params.path);
}

export async function POST(request: NextRequest, props: { params: Promise<{ path: string[] }> }) {
  const params = await props.params;
  return handle(request, params.path);
}

async function handle(request: NextRequest, path: string[]) {
  const backendUrl = process.env.BACKEND_URL || "http://localhost:8000";
  const pathStr = path.join("/");
  const url = new URL(request.url);
  const targetUrl = `${backendUrl}/api/${pathStr}${url.search}`;

  const headers = new Headers();
  request.headers.forEach((value, key) => {
    if (key.toLowerCase() !== "host") {
      headers.set(key, value);
    }
  });

  const method = request.method;
  let body: any = undefined;
  if (!["GET", "HEAD"].includes(method)) {
    try {
      body = await request.blob();
    } catch {
      body = undefined;
    }
  }

  try {
    const res = await fetch(targetUrl, {
      method,
      headers,
      body,
      // @ts-ignore
      duplex: "half",
    });

    const resHeaders = new Headers();
    res.headers.forEach((value, key) => {
      resHeaders.set(key, value);
    });

    return new NextResponse(res.body, {
      status: res.status,
      statusText: res.statusText,
      headers: resHeaders,
    });
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 502 });
  }
}

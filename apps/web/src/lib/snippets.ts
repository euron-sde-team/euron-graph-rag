/** Copy-paste examples for asking a project questions from code, the shell and CI. */

export type SnippetInput = {
  apiUrl: string;
  project: string;
  key: string;
};

export type Snippets = { curl: string; python: string; node: string };

const QUESTION = "Who founded Helios Robotics?";

export function snippets({ apiUrl, project, key }: SnippetInput): Snippets {
  const url = `${apiUrl}/api/v1/projects/${project}/query`;
  const curl = [
    `curl -s ${url} \\`,
    `  -H "authorization: Bearer ${key}" \\`,
    '  -H "content-type: application/json" \\',
    `  -d '{"question": "${QUESTION}", "mode": "hybrid"}'`,
  ].join("\n");
  const python = [
    "import httpx",
    "",
    "response = httpx.post(",
    `    "${url}",`,
    `    headers={"authorization": "Bearer ${key}"},`,
    `    json={"question": "${QUESTION}", "mode": "hybrid"},`,
    ")",
    "answer = response.json()",
    'print(answer["answer"])',
    'for source in answer["citations"]:',
    '    print(source["n"], source["label"])',
  ].join("\n");
  const node = [
    `const response = await fetch("${url}", {`,
    '  method: "POST",',
    `  headers: { authorization: "Bearer ${key}", "content-type": "application/json" },`,
    `  body: JSON.stringify({ question: "${QUESTION}", mode: "hybrid" }),`,
    "});",
    "const { answer, citations } = await response.json();",
  ].join("\n");
  return { curl, python, node };
}

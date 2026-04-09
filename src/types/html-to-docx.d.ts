declare module "html-to-docx" {
  type HtmlToDocx = (
    htmlString: string,
    headerHTMLString?: string | null,
    documentOptions?: Record<string, unknown>,
    footerHTMLString?: string | null
  ) => Promise<Buffer | Blob>

  const htmlToDocx: HtmlToDocx
  export default htmlToDocx
}

// The backend stores the raw file extension as the type, so one kind of document can have two values.
export const FILE_TYPE_GROUPS = [
  { key: 'pdf', label: 'PDF', extensions: ['pdf'] },
  { key: 'docx', label: 'Word', extensions: ['docx'] },
  { key: 'html', label: 'HTML', extensions: ['html', 'htm'] },
  { key: 'md', label: 'Markdown', extensions: ['md', 'markdown'] },
  { key: 'txt', label: 'Text', extensions: ['txt'] },
] as const

export const expandFileTypes = (keys: string[]) =>
  FILE_TYPE_GROUPS.filter((g) => keys.includes(g.key)).flatMap((g) => [...g.extensions])

export const fileTypeLabels = (keys: string[]) =>
  FILE_TYPE_GROUPS.filter((g) => keys.includes(g.key)).map((g) => g.label)

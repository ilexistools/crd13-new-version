// Templates (mvp-4.0)
// Components are now indexed ("1", "2", ...) and each component has a stable `label`
// that matches the <ComponentLabel> used in `structural_template`.

export interface TemplateComponent {
  label: string;
  text: string;
  required: boolean;
  description: string;
  examples: string[];
  allow_custom: boolean;
}

export interface TemplateItem {
  id: string;
  type: string;
  category: string;

  // Older template sets may include this; keep optional for compatibility.
  commodities?: string[];

  modality: string;
  communicative_function: string;
  representative_example: string;
  structural_template: string;

  // mvp-4.0: numeric keys -> component metadata
  components: { [key: string]: TemplateComponent };
}

export interface TemplatesRoot {
  version: string;
  items: TemplateItem[];
}

export interface EditorState {
  // Keys are component labels (e.g., "SubjectNounPhrase", "sentence")
  values: { [key: string]: string };
  choices: { [key: string]: string };
  optionals: { [key: string]: boolean };
}

export interface RequirementItem {
  id: string;
  templateId: string;
  sentence: string;
  state: EditorState;
  timestamp: number;
  commodity?: string;
  commodities?: string[];
}

export type TokenType = 'text' | 'component' | 'choice' | 'optional';

export interface Token {
  type: TokenType;
  value?: string;
  name?: string;
  required?: boolean;
  id?: string;
  options?: string[];
  children?: Token[];
}

export interface CollectedElements {
  components: Array<{ name: string; required: boolean }>;
  choices: Array<{ id: string; options: string[]; required: boolean }>;
  optionals: Array<{ id: string; children: Token[] }>;
}

import { Injectable } from '@angular/core';
import { Token, EditorState, CollectedElements } from '../models/template.models';

@Injectable({ providedIn: 'root' })
export class TemplateParserService {
  private choiceCounter = 0;
  private optionalCounter = 0;

  parseTemplate(template: string): Token[] {
    this.choiceCounter = 0;
    this.optionalCounter = 0;
    return this.parseSegment(template || '', 0, null).tokens;
  }

  private parseSegment(str: string, idx: number, end: string | null): { tokens: Token[]; next: number } {
    const tokens: Token[] = [];
    let i = idx;

    const pushText = (t: string) => {
      if (!t) return;
      const last = tokens[tokens.length - 1];
      if (last?.type === 'text') last.value += t;
      else tokens.push({ type: 'text', value: t });
    };

    while (i < str.length) {
      const ch = str[i];
      if (end && ch === end) return { tokens, next: i + 1 };

      if (ch === '{') {
        const optId = `opt_${++this.optionalCounter}`;
        const inner = this.parseSegment(str, i + 1, '}');
        tokens.push({ type: 'optional', id: optId, children: inner.tokens });
        i = inner.next;
        continue;
      }

      if (ch === '<') {
        const close = str.indexOf('>', i + 1);
        if (close === -1) {
          pushText(ch);
          i++;
          continue;
        }

        let required = i > 0 && str[i - 1] === '*';
        if (required && tokens.length && tokens[tokens.length - 1].type === 'text') {
          tokens[tokens.length - 1].value = (tokens[tokens.length - 1].value || '').replace(/\*$/, '');
        }

        tokens.push({ type: 'component', name: str.slice(i + 1, close).trim(), required });
        i = close + 1;
        continue;
      }

      if (ch === '[') {
        const close = str.indexOf(']', i + 1);
        if (close === -1) {
          pushText(ch);
          i++;
          continue;
        }

        let required = i > 0 && str[i - 1] === '*';
        if (required && tokens.length && tokens[tokens.length - 1].type === 'text') {
          tokens[tokens.length - 1].value = (tokens[tokens.length - 1].value || '').replace(/\*$/, '');
        }

        const id = `choice_${++this.choiceCounter}`;
        const options = str
          .slice(i + 1, close)
          .split('/')
          .map(x => x.trim())
          .filter(Boolean);

        tokens.push({ type: 'choice', id, options, required });
        i = close + 1;
        continue;
      }

      pushText(ch);
      i++;
    }

    return { tokens, next: i };
  }

  collectElements(tokens: Token[]): CollectedElements {
    const comps = new Map<string, boolean>();
    const choices: any[] = [];
    const optionals: any[] = [];

    const walk = (list: Token[]) => {
      for (const t of list) {
        if (t.type === 'component') {
          const prev = comps.get(t.name!);
          comps.set(t.name!, Boolean(prev || t.required));
        } else if (t.type === 'choice') {
          choices.push({ id: t.id, options: t.options, required: t.required });
        } else if (t.type === 'optional') {
          optionals.push({ id: t.id, children: t.children });
          walk(t.children || []);
        }
      }
    };

    walk(tokens);
    return {
      components: Array.from(comps.entries()).map(([name, req]) => ({ name, required: req })),
      choices,
      optionals
    };
  }

  renderSentence(tokens: Token[], state: EditorState, editedComponents?: Set<string>): string {
    const parts: string[] = [];

    const walk = (list: Token[]) => {
      for (const t of list) {
        if (t.type === 'text') {
          parts.push(t.value || '');
          continue;
        }

        if (t.type === 'component') {
          const isEdited = editedComponents ? editedComponents.has(t.name!) : true;
          if (isEdited) {
            const val = (state.values[t.name!] || '').trim();
            if (val) parts.push(val);
          } else {
            parts.push(`<${t.name}>`);
          }
          continue;
        }

        if (t.type === 'choice') {
          const val = (state.choices[t.id!] || '').trim();
          if (val) parts.push(val);
          continue;
        }

        if (t.type === 'optional') {
          if (state.optionals[t.id!]) walk(t.children || []);
          continue;
        }
      }
    };

    walk(tokens);
    return parts.join('').replace(/\s+/g, ' ').trim();
  }

  validate(collected: CollectedElements, state: EditorState, editedComponents?: Set<string>): string[] {
    const problems: string[] = [];
    for (const c of collected.components) {
      const isEdited = editedComponents ? editedComponents.has(c.name) : true;
      if (c.required && isEdited && !state.values[c.name]?.trim()) {
        problems.push(`"${c.name}" is required`);
      }
    }
    return problems;
  }
}
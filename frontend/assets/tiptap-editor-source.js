import { Editor, mergeAttributes, Node } from '@tiptap/core';
import StarterKit from '@tiptap/starter-kit';
import { Selection } from '@tiptap/pm/state';

const QALine = Node.create({
  name: 'qaLine',
  group: 'block',
  content: 'inline*',
  defining: true,
  addAttributes() {
    return { kind: { default: 'question' } };
  },
  parseHTML() {
    return [{ tag: 'div[data-qa-kind]', getAttrs: element => ({ kind: element.getAttribute('data-qa-kind') === 'answer' ? 'answer' : 'question' }) }];
  },
  renderHTML({ node, HTMLAttributes }) {
    const label = node.attrs.kind === 'answer' ? '答：' : '问：';
    return ['div', mergeAttributes({ class: 'qa-line', 'data-qa-kind': node.attrs.kind }, HTMLAttributes), ['span', { class: 'qa-label' }, label], ['span', { class: 'qa-answer' }, 0]];
  },
  addKeyboardShortcuts() {
    return {
      Enter: () => {
        const { state, view } = this.editor;
        const { $from } = state.selection;
        if ($from.parent.type.name !== 'qaLine') return false;
        const position = $from.after();
        const nextKind = $from.parent.attrs.kind === 'question' ? 'answer' : 'question';
        const transaction = state.tr.insert(position, state.schema.nodes.qaLine.create({ kind: nextKind }));
        view.dispatch(transaction.setSelection(Selection.near(transaction.doc.resolve(position + 1))).scrollIntoView());
        return true;
      },
    };
  },
});

const InputField = Node.create({
  name: 'inputField',
  inline: true,
  group: 'inline',
  content: 'text*',
  defining: true,
  addAttributes() {
    return { name: { default: '' } };
  },
  parseHTML() {
    return [{ tag: 'span[data-field-name]', getAttrs: element => ({ name: element.getAttribute('data-field-name') || '' }) }];
  },
  renderHTML({ node, HTMLAttributes }) {
    return ['span', mergeAttributes({ class: 'inline-field', 'data-field-name': node.attrs.name }, HTMLAttributes), 0];
  },
  addKeyboardShortcuts() {
    return {
      Enter: () => {
        const { state, view } = this.editor;
        const { $from } = state.selection;
        let fieldPosition = null;
        for (let depth = $from.depth; depth > 0; depth -= 1) {
          if ($from.node(depth).type.name === 'inputField') {
            fieldPosition = $from.before(depth);
            break;
          }
        }
        if (fieldPosition === null) return false;
        const positions = [];
        state.doc.descendants((node, position) => {
          if (node.type.name === 'inputField') positions.push(position);
        });
        const nextPosition = positions.find(position => position > fieldPosition) ?? positions[0];
        if (nextPosition === undefined || nextPosition === fieldPosition) return true;
        const transaction = state.tr.setSelection(Selection.near(state.doc.resolve(nextPosition + 1))).scrollIntoView();
        view.dispatch(transaction);
        return true;
      },
    };
  },
});

window.StreamUiTiptap = function mountTranscriptEditor(element, content, editable, onUpdate) {
  return new Editor({
    element,
    extensions: [StarterKit, QALine, InputField],
    content,
    editable,
    editorProps: { attributes: { class: 'transcript-prosemirror' } },
    onUpdate: ({ editor }) => onUpdate(editor.getJSON()),
  });
};
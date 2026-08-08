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

window.StreamUiTiptap = function mountTranscriptEditor(element, content, editable, onUpdate) {
  return new Editor({
    element,
    extensions: [StarterKit, QALine],
    content,
    editable,
    editorProps: { attributes: { class: 'transcript-prosemirror' } },
    onUpdate: ({ editor }) => onUpdate(editor.getJSON()),
  });
};
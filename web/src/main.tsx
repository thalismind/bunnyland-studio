import { render } from 'preact';

import { App } from './App';
import './styles.css';

const root = document.getElementById('app');
if (!root) throw new Error('Studio root element is missing');
render(<App />, root);

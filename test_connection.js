const fetch = require('node-fetch');

async function test() {
  try {
    console.log('Testing connection to backend...');
    const response = await fetch('http://localhost:8000/health');
    const data = await response.json();
    console.log('Success:', data);
  } catch (err) {
    console.log('Error:', err.message);
  }
}

test();
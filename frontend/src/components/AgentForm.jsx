import React from 'react';
import { useState } from 'react';

export default function AgentForm({ addAgent }) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [image, setImage] = useState(null);
  const [pdf, setPdf] = useState(null);

  const handleSubmit = () => {
    if (!name) return alert('Agent name required');
    addAgent({ name, description, image: image ? URL.createObjectURL(image) : null, pdf: pdf ? URL.createObjectURL(pdf) : null });
  };

  return (
    <div className="bg-white p-6 rounded-xl shadow mb-6">
      <h3 className="text-lg font-bold mb-4">Create New Chatbot</h3>
      <input className="w-full p-3 border rounded mb-4" placeholder="Agent Name" value={name} onChange={e => setName(e.target.value)} />
      <input className="w-full p-3 border rounded mb-4" placeholder="Description" value={description} onChange={e => setDescription(e.target.value)} />
      <label className="block mb-2">
        <span className="text-gray-700">Upload Image</span>
        <input type="file" accept="image/*" className="mt-1 block w-full" onChange={e => setImage(e.target.files[0])} />
      </label>
      <label className="block mb-4">
        <span className="text-gray-700">Upload PDF</span>
        <input type="file" accept="application/pdf" className="mt-1 block w-full" onChange={e => setPdf(e.target.files[0])} />
      </label>
      <button className="bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700 transition" onClick={handleSubmit}>Create Agent</button>
    </div>
  );
}

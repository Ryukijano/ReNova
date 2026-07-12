import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import '@testing-library/jest-dom';
import App from './App';
import { API_BASE_URL } from './config';

describe('ReNova ADMET App', () => {
  it('renders the disease input field with default value', () => {
    render(<App />);
    const inputElement = screen.getByLabelText(/Disease Query/i);
    expect(inputElement).toBeInTheDocument();
    expect(inputElement).toHaveValue('cystic fibrosis');
  });

  it('renders the mock mode checkbox and it is checked by default', () => {
    render(<App />);
    const checkboxElement = screen.getByLabelText(/Use API Simulation/i);
    expect(checkboxElement).toBeInTheDocument();
    expect(checkboxElement).toBeChecked();
  });

  it('renders the submit button with correct text', () => {
    render(<App />);
    const buttonElement = screen.getByRole('button', { name: /Execute Pipeline/i });
    expect(buttonElement).toBeInTheDocument();
    expect(buttonElement).not.toBeDisabled();
  });

  it('configures the API URL correctly to the Hugging Face Space', () => {
    expect(API_BASE_URL).toBe('https://ryukijano-catcon-one-shot-controlnet-sd-1-5-b2.hf.space');
  });
});


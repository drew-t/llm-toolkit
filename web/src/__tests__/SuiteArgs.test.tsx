import { fireEvent, render, screen } from '@testing-library/preact'
import { describe, expect, it, vi } from 'vitest'
import { SuiteArgs } from '../pages/run/SuiteArgs'

describe('SuiteArgs', () => {
  it('renders fields for throughput_benchy', () => {
    render(<SuiteArgs benchmark="throughput_benchy" value={{}} onChange={() => {}} />)
    expect(screen.getByLabelText(/pp/i)).toBeTruthy()
    expect(screen.getByLabelText(/tg/i)).toBeTruthy()
    expect(screen.getByLabelText(/tokenizer/i)).toBeTruthy()
  })

  it('renders nothing for context_scaling', () => {
    const { container } = render(
      <SuiteArgs benchmark="context_scaling" value={{}} onChange={() => {}} />
    )
    expect(container.textContent).toContain('No extra arguments')
  })

  it('emits parsed list values', () => {
    const onChange = vi.fn()
    render(<SuiteArgs benchmark="throughput_benchy" value={{}} onChange={onChange} />)
    fireEvent.input(screen.getByLabelText(/pp/i), { target: { value: '2048,4096' } })
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ pp: [2048, 4096] }))
  })
})

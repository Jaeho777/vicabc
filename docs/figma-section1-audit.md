# VIC Figma Section 1 audit

Source: Figma file `VIC`, `Section 1`.

This audit compares the annotated public canvas against the live Flask
templates. The Figma API account still cannot read layer metadata or design
tokens, so exact numeric token comparison remains blocked. Screen structure,
visible annotations, interactions, and responsive behavior were checked.

## Main

- [x] Compared all three main variants
- [x] Latest `main ver.3` structure is used
- [x] Welcome, product status, notices, and today's learning are present
- [x] Math remains as an intentional fourth product required by the live site

## VOCA - 7 screens

- [x] Curriculum and grade selection
- [x] Word list, progress, status, and random practice entry
- [x] Listening initial and replay states
- [x] Speaking, recording, and replay states
- [x] Writing state
- [x] Result and next-word state
- [x] Repeated action buttons now share consistent size, position, and colors

## Bible Story - 5 screens

- [x] Grade selection and chapter quick jump
- [x] Grade chapter list
- [x] Chapter story list and progress
- [x] Story listening, speaking, writing, scoring, and save controls
- [x] Practice cards now use the shared compact radius and flat surface style

## Village - 3 screens

- [x] Village selection and recent progress
- [x] Lesson jump strip and lesson card list
- [x] One selected lesson practice panel at a time
- [x] Practice controls and result panels moved to the right column
- [x] Added the annotated fixed `TOP` control
- [x] Listening, speaking, replay, checking, and writing behavior retained

## Shared annotation

- [x] Header, card density, button dimensions, and surface treatment normalized
- [x] VOCA, Bible Story, and Village accents keep distinct identities while
      using comparable saturation, spacing, borders, and interaction states
- [ ] Exact layer dimensions, font tokens, and exported assets require Figma
      editor access for API verification

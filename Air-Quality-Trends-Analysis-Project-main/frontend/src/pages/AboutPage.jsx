import React, { useState, useEffect } from "react";
import axios from "axios";
import Header from "../components/Header";

const API = import.meta.env.VITE_API_BASE ?? "";

export default function AboutPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;
    axios
      .get(`${API}/about/health`)
      .then((res) => {
        if (isMounted) setData(res.data);
      })
      .catch((err) => {
        console.warn("Using fallback health guide data:", err);
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, []);

  const groups = data?.groups || {
    low: {
      label: "Low AQI (Good - Satisfactory, 0-100)",
      summary: "Air is largely safe. Only unusually sensitive people may notice minor discomfort.",
    },
    medium: {
      label: "Medium AQI (Moderate, 101-200)",
      summary: "Healthy adults are usually fine; asthma, heart and lung patients, children and older adults may feel symptoms and should take it easier outdoors.",
    },
    high: {
      label: "High AQI (Poor - Severe, 201-500)",
      summary: "Health effects reach most people on prolonged exposure and become serious for everyone, especially at-risk groups, at the top of the scale.",
    },
  };

  const categories = data?.categories || [
    {
      key: "good",
      label: "Good",
      range: "0-50",
      color: "#1E9E57",
      cpcb_statement: "Minimal impact.",
      who_is_affected: "Almost no one.",
      what_you_may_feel: "Nothing noticeable.",
      what_to_do: ["Normal outdoor activity is fine for everyone."],
    },
    {
      key: "satisfactory",
      label: "Satisfactory",
      range: "51-100",
      color: "#8BC34A",
      cpcb_statement: "May cause minor breathing discomfort to sensitive people.",
      who_is_affected: "Unusually sensitive people, e.g. some with asthma.",
      what_you_may_feel: "Occasional mild cough or throat irritation in sensitive people.",
      what_to_do: ["Outdoor activity is fine for most people.", "Sensitive people can watch for symptoms."],
    },
    {
      key: "moderate",
      label: "Moderate",
      range: "101-200",
      color: "#F4C20D",
      cpcb_statement: "May cause breathing discomfort to people with lung disease such as asthma, and discomfort to people with heart disease, children and older adults.",
      who_is_affected: "People with asthma, COPD or heart disease; children; older adults.",
      what_you_may_feel: "Cough, wheeze or breathlessness in at-risk groups, especially during exercise.",
      what_to_do: [
        "At-risk groups: shorten or ease strenuous outdoor activity.",
        "Keep rescue inhalers and prescribed medicines at hand.",
        "Healthy adults can usually continue normal activity.",
      ],
    },
    {
      key: "poor",
      label: "Poor",
      range: "201-300",
      color: "#F28C28",
      cpcb_statement: "May cause breathing discomfort to most people on prolonged exposure, and discomfort to people with heart disease.",
      who_is_affected: "Most people on prolonged exposure; at-risk groups more strongly.",
      what_you_may_feel: "Throat and eye irritation, cough, tiredness, breathlessness when active.",
      what_to_do: [
        "Reduce prolonged or heavy outdoor exercise.",
        "Consider a well-fitted N95/FFP2 mask outdoors (cloth and surgical masks filter little PM2.5).",
        "Keep windows closed in the worst hours; use an air purifier if you have one.",
      ],
    },
    {
      key: "very_poor",
      label: "Very Poor",
      range: "301-400",
      color: "#D32F2F",
      cpcb_statement: "May cause respiratory illness to people on prolonged exposure. Effect may be more pronounced in people with lung and heart diseases.",
      who_is_affected: "Everyone on prolonged exposure; at-risk groups can become seriously unwell.",
      what_you_may_feel: "Persistent cough, chest tightness, worsening asthma or heart symptoms.",
      what_to_do: [
        "Avoid outdoor exercise; limit time outside.",
        "Wear a well-fitted N95/FFP2 mask if you must go out.",
        "Seek medical advice early if you have chest pain, severe breathlessness or worsening symptoms.",
      ],
    },
    {
      key: "severe",
      label: "Severe",
      range: "401-500",
      color: "#7B1113",
      cpcb_statement: "Affects healthy people and seriously impacts those with existing diseases.",
      who_is_affected: "Everyone; people with existing disease are seriously affected.",
      what_you_may_feel: "Marked breathing difficulty, eye and throat irritation, fatigue; serious risk for at-risk groups.",
      what_to_do: [
        "Stay indoors with windows closed where possible; avoid all outdoor exertion.",
        "Use an N95/FFP2 mask outdoors and an air purifier indoors if available.",
        "Get medical help promptly for chest pain, severe breathlessness, fainting or confusion.",
      ],
    },
  ];

  const whyPm25 =
    data?.why_pm25_matters ||
    "PM2.5 particles are smaller than 2.5 micrometres—about 30 times finer than a human hair. They travel deep into the lungs and can cross into the bloodstream. Long-term exposure is linked to asthma, COPD, heart attacks, stroke, and impaired lung development in children.";

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <Header />

      <main className="flex-1 max-w-5xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-10">
        {/* Page Header */}
        <div className="mb-10 text-center sm:text-left">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 mb-3">
            <span>CPCB Standards & Health Guidance</span>
          </div>
          <h1 className="text-3xl sm:text-4xl font-extrabold text-gray-900 tracking-tight">
            Air Quality & Health Guide
          </h1>
          <p className="mt-2 text-base sm:text-lg text-gray-600 max-w-3xl">
            A practical explanation of the Central Pollution Control Board (CPCB) AQI scale,
            particulate matter health impacts, and recommended precautions for vulnerable groups.
          </p>
        </div>

        {/* 3-Group High Level Summary */}
        <section className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
          {Object.entries(groups).map(([key, group]) => {
            const borderColors = {
              low: "border-emerald-500 bg-emerald-50/40",
              medium: "border-yellow-500 bg-yellow-50/40",
              high: "border-red-500 bg-red-50/40",
            };

            return (
              <div
                key={key}
                className={`p-6 rounded-2xl border-l-4 border-t border-r border-b border-gray-200 bg-white shadow-sm ${borderColors[key]}`}
              >
                <h3 className="font-bold text-gray-900 text-base mb-2">{group.label}</h3>
                <p className="text-xs sm:text-sm text-gray-600 leading-relaxed">{group.summary}</p>
              </div>
            );
          })}
        </section>

        {/* Detailed 6 CPCB Categories */}
        <section className="mb-12">
          <h2 className="text-2xl font-bold text-gray-900 mb-6">
            Detailed CPCB Air Quality Bands & Guidance
          </h2>

          <div className="space-y-4">
            {categories.map((c) => (
              <div
                key={c.key}
                className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm border-l-8 transition-shadow hover:shadow-md"
                style={{ borderLeftColor: c.color }}
              >
                <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
                  <div className="flex items-center gap-3">
                    <span className="font-extrabold text-lg text-gray-900">{c.label}</span>
                    <span
                      className="px-2.5 py-0.5 rounded text-xs font-bold text-white uppercase"
                      style={{ backgroundColor: c.color }}
                    >
                      AQI {c.range}
                    </span>
                  </div>
                  <span className="text-xs italic text-gray-500">&quot;{c.cpcb_statement}&quot;</span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs text-gray-700 mt-3 pt-3 border-t border-gray-100">
                  <div>
                    <span className="font-bold text-gray-900 block mb-1">Who is affected:</span>
                    <span>{c.who_is_affected}</span>
                  </div>

                  <div>
                    <span className="font-bold text-gray-900 block mb-1">Noticeable symptoms:</span>
                    <span>{c.what_you_may_feel}</span>
                  </div>

                  <div>
                    <span className="font-bold text-gray-900 block mb-1">Recommended actions:</span>
                    <ul className="list-disc list-inside space-y-1">
                      {c.what_to_do.map((item, idx) => (
                        <li key={idx}>{item}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Why PM2.5 Matters */}
        <section className="bg-white border border-gray-200 rounded-2xl p-6 sm:p-8 mb-10 shadow-sm">
          <h2 className="text-xl font-bold text-gray-900 mb-3 flex items-center gap-2">
            <span>🔬 Why PM2.5 Matters</span>
          </h2>
          <p className="text-sm text-gray-700 leading-relaxed">{whyPm25}</p>
        </section>

        {/* Standards Table: India NAAQS vs WHO 2021 */}
        <section className="bg-white border border-gray-200 rounded-2xl p-6 sm:p-8 mb-10 shadow-sm">
          <h2 className="text-xl font-bold text-gray-900 mb-2">
            Air Quality Standards Comparison
          </h2>
          <p className="text-xs text-gray-500 mb-6">
            Comparing India&apos;s National Ambient Air Quality Standards (NAAQS) with the World Health Organization (WHO 2021) guidelines.
          </p>

          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-xs sm:text-sm">
              <thead>
                <tr className="border-b border-gray-200 text-gray-500 uppercase font-semibold">
                  <th className="py-3 px-4">Pollutant Metric</th>
                  <th className="py-3 px-4">India NAAQS (2009)</th>
                  <th className="py-3 px-4">WHO Guideline (2021)</th>
                  <th className="py-3 px-4">Standard Purpose</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 text-gray-700">
                <tr>
                  <td className="py-3 px-4 font-semibold text-gray-900">PM2.5 (24-hour mean)</td>
                  <td className="py-3 px-4 text-emerald-800 font-bold">60 μg/m³</td>
                  <td className="py-3 px-4 text-blue-800 font-bold">15 μg/m³</td>
                  <td className="py-3 px-4 text-xs text-gray-500">Protection against acute respiratory events</td>
                </tr>
                <tr>
                  <td className="py-3 px-4 font-semibold text-gray-900">PM2.5 (Annual mean)</td>
                  <td className="py-3 px-4 text-emerald-800 font-bold">40 μg/m³</td>
                  <td className="py-3 px-4 text-blue-800 font-bold">5 μg/m³</td>
                  <td className="py-3 px-4 text-xs text-gray-500">Long-term cardiovascular & lung longevity</td>
                </tr>
                <tr>
                  <td className="py-3 px-4 font-semibold text-gray-900">PM10 (24-hour mean)</td>
                  <td className="py-3 px-4 text-emerald-800 font-bold">100 μg/m³</td>
                  <td className="py-3 px-4 text-blue-800 font-bold">45 μg/m³</td>
                  <td className="py-3 px-4 text-xs text-gray-500">Coarse dust & mechanical irritation</td>
                </tr>
                <tr>
                  <td className="py-3 px-4 font-semibold text-gray-900">PM10 (Annual mean)</td>
                  <td className="py-3 px-4 text-emerald-800 font-bold">60 μg/m³</td>
                  <td className="py-3 px-4 text-blue-800 font-bold">15 μg/m³</td>
                  <td className="py-3 px-4 text-xs text-gray-500">Chronic bronchitis prevention</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        {/* Disclaimer Notice */}
        <section className="bg-amber-50 border border-amber-200 rounded-2xl p-6 text-xs text-amber-900 leading-relaxed mb-8">
          <div className="flex items-start gap-3">
            <span className="text-xl">⚠️</span>
            <div>
              <span className="font-bold">Medical Disclaimer: </span>
              {data?.disclaimer ||
                "This platform provides public information and educational environmental analytics, not individualized medical advice. Persons with chronic pulmonary or cardiovascular conditions, pregnant women, young children, and the elderly should follow their physician's treatment plan."}
            </div>
          </div>
        </section>

        {/* Sources */}
        <section className="text-xs text-gray-500 space-y-1">
          <div className="font-semibold text-gray-700">Official Sources & Methodology:</div>
          <ul className="list-disc list-inside space-y-0.5">
            <li>Central Pollution Control Board (CPCB) National Air Quality Index (2014)</li>
            <li>World Health Organization (WHO) Global Air Quality Guidelines (2021)</li>
            <li>Central Pollution Control Board National Ambient Air Quality Standards (2009)</li>
            <li>OpenAQ v3 Platform & Open-Meteo Atmospheric Model Integration</li>
          </ul>
        </section>
      </main>
    </div>
  );
}
